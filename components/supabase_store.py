"""
components/supabase_store.py
Supabase-backed persistent store — all queries scoped by user_id.
Function signatures match what server.py expects.
"""

import os
import random
import string
import time
from datetime import datetime
from typing import Optional

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL     = os.getenv("SUPABASE_URL")
# CORRECT
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

MAX_PLAYERS = 5


# ── Code generator ─────────────────────────────────────────────────────────────

def _make_code() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=4))
    digits  = "".join(random.choices(string.digits, k=4))
    return f"{letters}-{digits}"


# ── Session assembler ──────────────────────────────────────────────────────────

def _build_session_dict(session_row: dict) -> dict:
    """Fetch players + answers and return a unified session dict."""
    sid = session_row["id"]

    players_resp = (
        _client.table("session_players")
        .select("*")
        .eq("session_id", sid)
        .order("joined_at")
        .execute()
    )
    players_rows = players_resp.data or []

    players = []
    for p in players_rows:
        answers_resp = (
            _client.table("answers")
            .select("*")
            .eq("player_id", p["id"])
            .order("q_index")
            .execute()
        )
        answers = [
            {
                "q_index":    a["q_index"],
                "chosen":     a["chosen"],
                "correct":    a["correct"],
                "got":        a["got"],
                "pts":        a["pts"],
                "time_taken": a["time_taken"],
            }
            for a in (answers_resp.data or [])
        ]
        players.append({
            "name":      p["display_name"],
            "is_host":   p["is_host"],
            "score":     p["score"],
            "q_index":   p["q_index"],
            "finished":  p["finished"],
            "joined_at": p["joined_at"],
            "answers":   answers,
            "player_id": p["id"],
            "user_id":   p.get("user_id"),
        })

    return {
        "id":               session_row["id"],
        "code":             session_row["code"],
        "host":             session_row["host_name"],
        "question_set_id":  session_row["question_set_id"],
        "qs_title":         session_row.get("qs_title", ""),
        "password":         session_row.get("password", ""),
        "status":           session_row["status"],
        "players":          players,
        "created_at":       session_row["created_at"],
        "started_at":       session_row.get("started_at"),
        "finished_at":      session_row.get("finished_at"),
        "host_user_id":     session_row.get("host_user_id"),
    }


# ── Materials ──────────────────────────────────────────────────────────────────

def save_material(title: str, text: str, user_id: str, tags: str = "") -> dict:
    row = {
        "title":     title,
        "text":      text,
        "tags":      tags,
        "is_public": False,       # private by default — only visible to owner
        "user_id":   user_id,
    }
    resp = _client.table("materials").insert(row).execute()
    data = resp.data[0]
    data["uploader"] = user_id
    return data


def get_user_materials(user_id: str) -> list:
    """Return all materials uploaded by this user."""
    resp = (
        _client.table("materials")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_material(mid: str, user_id: str) -> Optional[dict]:
    """Return a material only if it belongs to user_id."""
    resp = (
        _client.table("materials")
        .select("*")
        .eq("id", mid)
        .eq("user_id", user_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


# ── Question sets ──────────────────────────────────────────────────────────────

def save_question_set(qs: dict, user_id: str) -> dict:
    row = {
        "title":      qs.get("title"),
        "subject":    qs.get("subject"),
        "time_limit": qs.get("time_limit", 15),
        "difficulty": qs.get("difficulty"),
        "questions":  qs.get("questions"),   # stored as JSONB
        "is_public":  False,
        "user_id":    user_id,
    }
    resp = _client.table("question_sets").insert(row).execute()
    saved = resp.data[0]
    return {**qs, **saved, "uploader": user_id, "is_public": False}


def get_user_question_sets(user_id: str) -> list:
    """Return all question sets created by this user."""
    resp = (
        _client.table("question_sets")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def publish_question_set(qid: str, user_id: str) -> Optional[dict]:
    """Publish a question set — only if it belongs to user_id."""
    resp = (
        _client.table("question_sets")
        .update({"is_public": True})
        .eq("id", qid)
        .eq("user_id", user_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_question_set(qid: str, user_id: Optional[str] = None) -> Optional[dict]:
    """
    Return a question set.
    If user_id provided, must match (owner check).
    If not provided (internal use like session lookup), returns regardless of owner.
    """
    query = _client.table("question_sets").select("*").eq("id", qid)
    if user_id:
        query = query.eq("user_id", user_id)
    resp = query.execute()
    return resp.data[0] if resp.data else None


def _get_question_set_any(qid: str) -> Optional[dict]:
    """Internal: fetch question set without user scope (for session creation)."""
    resp = _client.table("question_sets").select("*").eq("id", qid).execute()
    return resp.data[0] if resp.data else None


# ── Sessions ───────────────────────────────────────────────────────────────────

def create_session(host_name: str, question_set_id: str, password: str = "", user_id: str = "") -> dict:
    qs = _get_question_set_any(question_set_id)
    if not qs:
        raise ValueError("Question set not found")

    code = _make_code()
    while True:
        check = _client.table("sessions").select("id").eq("code", code).execute()
        if not check.data:
            break
        code = _make_code()

    session_row = {
        "code":             code,
        "host_name":        host_name,
        "host_user_id":     user_id,
        "question_set_id":  question_set_id,
        "qs_title":         qs.get("title", "Untitled"),
        "password":         password,
        "status":           "waiting",
    }
    resp = _client.table("sessions").insert(session_row).execute()
    session = resp.data[0]

    player_row = {
        "session_id":   session["id"],
        "display_name": host_name,
        "user_id":      user_id,
        "is_host":      True,
        "score":        0,
        "q_index":      0,
        "finished":     False,
    }
    _client.table("session_players").insert(player_row).execute()

    return _build_session_dict(session)


def get_session_by_code(code: str) -> Optional[dict]:
    resp = (
        _client.table("sessions")
        .select("*")
        .eq("code", code.upper().strip())
        .execute()
    )
    if not resp.data:
        return None
    return _build_session_dict(resp.data[0])


def get_session(sid: str) -> Optional[dict]:
    resp = _client.table("sessions").select("*").eq("id", sid).execute()
    if not resp.data:
        return None
    return _build_session_dict(resp.data[0])


def get_open_sessions() -> list:
    resp = (
        _client.table("sessions")
        .select("*")
        .eq("status", "waiting")
        .order("created_at", desc=True)
        .execute()
    )
    return [_build_session_dict(s) for s in (resp.data or [])]


def join_session(code: str, player_name: str, password: str = "", user_id: str = "") -> tuple:
    resp = (
        _client.table("sessions")
        .select("*")
        .eq("code", code.upper().strip())
        .execute()
    )
    if not resp.data:
        raise ValueError("Session not found")

    session_row = resp.data[0]
    sid = session_row["id"]

    if session_row["status"] != "waiting":
        raise ValueError("Session already started or finished")
    if session_row.get("password") and session_row["password"] != password:
        raise ValueError("Wrong password")

    count_resp = (
        _client.table("session_players")
        .select("id", count="exact")
        .eq("session_id", sid)
        .execute()
    )
    if (count_resp.count or 0) >= MAX_PLAYERS:
        raise ValueError(f"Session full ({MAX_PLAYERS} players max)")

    name_check = (
        _client.table("session_players")
        .select("id")
        .eq("session_id", sid)
        .eq("display_name", player_name)
        .execute()
    )
    if name_check.data:
        raise ValueError("Name already taken in this session")

    player_row = {
        "session_id":   sid,
        "display_name": player_name,
        "user_id":      user_id,
        "is_host":      False,
        "score":        0,
        "q_index":      0,
        "finished":     False,
    }
    p_resp = _client.table("session_players").insert(player_row).execute()
    p_data = p_resp.data[0]

    session_dict = _build_session_dict(session_row)
    player_dict  = {
        "name":      player_name,
        "is_host":   False,
        "score":     0,
        "q_index":   0,
        "answers":   [],
        "finished":  False,
        "joined_at": p_data["joined_at"],
    }
    return session_dict, player_dict


def start_session(code: str, host_name: str) -> dict:
    resp = (
        _client.table("sessions")
        .select("*")
        .eq("code", code.upper().strip())
        .eq("host_name", host_name)
        .execute()
    )
    if not resp.data:
        raise ValueError("Session not found or not host")

    session_row = resp.data[0]
    updated = (
        _client.table("sessions")
        .update({"status": "started", "started_at": datetime.utcnow().isoformat()})
        .eq("id", session_row["id"])
        .execute()
    )
    return _build_session_dict(updated.data[0])


def submit_answer(code: str, player_name: str, q_index: int,
                  chosen: str, correct: str, pts: int, time_taken: float) -> dict:
    s_resp = (
        _client.table("sessions")
        .select("*")
        .eq("code", code.upper().strip())
        .execute()
    )
    if not s_resp.data:
        raise ValueError("Session not found")
    session_row = s_resp.data[0]
    sid = session_row["id"]

    p_resp = (
        _client.table("session_players")
        .select("*")
        .eq("session_id", sid)
        .eq("display_name", player_name)
        .execute()
    )
    if not p_resp.data:
        raise ValueError("Player not found in session")
    player = p_resp.data[0]
    pid = player["id"]

    answer_row = {
        "session_id":   sid,
        "player_id":    pid,
        "display_name": player_name,
        "user_id":      player.get("user_id"),
        "q_index":      q_index,
        "chosen":       chosen,
        "correct":      correct,
        "got":          pts > 0,
        "pts":          pts,
        "time_taken":   round(time_taken, 2),
    }
    _client.table("answers").insert(answer_row).execute()

    _client.table("session_players").update({
        "score":   player["score"] + pts,
        "q_index": q_index + 1,
    }).eq("id", pid).execute()

    return _build_session_dict(session_row)


def finish_player(code: str, player_name: str) -> dict:
    s_resp = (
        _client.table("sessions")
        .select("*")
        .eq("code", code.upper().strip())
        .execute()
    )
    if not s_resp.data:
        raise ValueError("Session not found")
    session_row = s_resp.data[0]
    sid = session_row["id"]

    _client.table("session_players").update({"finished": True}).eq(
        "session_id", sid
    ).eq("display_name", player_name).execute()

    all_resp = (
        _client.table("session_players")
        .select("finished")
        .eq("session_id", sid)
        .execute()
    )
    all_finished = all(p["finished"] for p in (all_resp.data or []))
    if all_finished:
        _client.table("sessions").update({
            "status":      "finished",
            "finished_at": datetime.utcnow().isoformat(),
        }).eq("id", sid).execute()

    updated = _client.table("sessions").select("*").eq("id", sid).execute()
    return _build_session_dict(updated.data[0])


# ── User history ───────────────────────────────────────────────────────────────

def get_user_session_history(user_id: str) -> list:
    """
    Return all sessions where the user participated as a player,
    with their personal score and answers for each.
    """
    # Find all player rows for this user
    players_resp = (
        _client.table("session_players")
        .select("*, sessions(*)")
        .eq("user_id", user_id)
        .order("joined_at", desc=True)
        .execute()
    )

    history = []
    for p in (players_resp.data or []):
        session_row = p.get("sessions", {})
        if not session_row:
            continue

        answers_resp = (
            _client.table("answers")
            .select("*")
            .eq("player_id", p["id"])
            .order("q_index")
            .execute()
        )
        answers = answers_resp.data or []

        total    = len(answers)
        correct  = sum(1 for a in answers if a.get("got"))
        accuracy = round((correct / total) * 100) if total else 0

        history.append({
            "session_id":      session_row.get("id"),
            "session_code":    session_row.get("code"),
            "qs_title":        session_row.get("qs_title", "Untitled"),
            "question_set_id": session_row.get("question_set_id"),
            "session_status":  session_row.get("status"),
            "started_at":      session_row.get("started_at"),
            "finished_at":     session_row.get("finished_at"),
            "is_host":         p.get("is_host", False),
            "display_name":    p.get("display_name"),
            "score":           p.get("score", 0),
            "q_index":         p.get("q_index", 0),
            "finished":        p.get("finished", False),
            "total_questions": total,
            "correct":         correct,
            "accuracy":        accuracy,
            "answers":         answers,
        })

    return history
