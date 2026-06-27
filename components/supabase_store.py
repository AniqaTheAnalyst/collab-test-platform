"""
components/supabase_store.py
Supabase-backed persistent store — drop-in replacement for session_store.py.
All function signatures match session_store.py exactly so server.py needs zero changes.
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

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")

_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

MAX_PLAYERS = 5


# ── Code generator ────────────────────────────────────────────────────────────

def _make_code() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=4))
    digits = "".join(random.choices(string.digits, k=4))
    return f"{letters}-{digits}"


# ── Internal session builder ──────────────────────────────────────────────────
# Reconstructs the same dict shape that server.py / frontend expect,
# assembling players + answers from their own tables.

def _build_session_dict(session_row: dict) -> dict:
    """
    Fetches session_players (+ their answers) and returns a session dict
    that looks identical to what the old JSON store returned.
    """
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
                "q_index": a["q_index"],
                "chosen":  a["chosen"],
                "correct": a["correct"],
                "got":     a["got"],
                "pts":     a["pts"],
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
            # keep the Supabase player id accessible for internal use
            "_player_id": p["id"],
        })

    return {
        "id":              session_row["id"],
        "code":            session_row["code"],
        "host":            session_row["host_name"],
        "question_set_id": session_row["question_set_id"],
        "qs_title":        session_row.get("qs_title", ""),
        "password":        session_row.get("password", ""),
        "status":          session_row["status"],
        "players":         players,
        "created_at":      session_row["created_at"],
        "started_at":      session_row.get("started_at"),
        "finished_at":     session_row.get("finished_at"),
    }


# ── Materials ─────────────────────────────────────────────────────────────────

def save_material(title: str, text: str, uploader: str, tags: str = "") -> dict:
    row = {
        "title":    title,
        "text":     text,
        "tags":     tags,
        "is_public": True,  # materials always public so they appear in the list
        # store uploader in user_id as text stub until Phase 2 auth
        "user_id":  None,
    }
    resp = _client.table("materials").insert(row).execute()
    data = resp.data[0]
    # inject uploader for frontend compatibility (not a DB column yet)
    data["uploader"] = uploader
    # store uploader name in tags if tags empty, for display
    if not data.get("tags"):
        data["tags"] = f"uploaded by {uploader}"
    return data


def _inject_uploader(m: dict) -> dict:
    """Extract uploader name from tags for display until Phase 2 auth."""
    if not m.get("uploader"):
        tags = m.get("tags", "")
        if tags.startswith("uploaded by "):
            m["uploader"] = tags.replace("uploaded by ", "")
        else:
            m["uploader"] = "unknown"
    return m


def get_all_materials() -> list:
    resp = _client.table("materials").select("*").order("created_at", desc=True).execute()
    return [_inject_uploader(m) for m in (resp.data or [])]


def get_material(mid: str) -> Optional[dict]:
    resp = _client.table("materials").select("*").eq("id", mid).execute()
    return _inject_uploader(resp.data[0]) if resp.data else None


# ── Question sets ─────────────────────────────────────────────────────────────

def save_question_set(qs: dict, uploader: str = "") -> dict:
    row = {
        "title":       qs.get("title"),
        "subject":     qs.get("subject"),
        "time_limit":  qs.get("time_limit", 15),
        "difficulty":  qs.get("difficulty"),
        "questions":   qs.get("questions"),   # stored as JSONB
        "is_public":   False,
    }
    resp = _client.table("question_sets").insert(row).execute()
    saved = resp.data[0]
    # return a dict that looks like what the old store returned
    return {**qs, **saved, "uploader": uploader, "is_public": False}


def get_all_question_sets() -> list:
    resp = (
        _client.table("question_sets")
        .select("*")
        .eq("is_public", True)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def publish_question_set(qid: str) -> Optional[dict]:
    resp = (
        _client.table("question_sets")
        .update({"is_public": True})
        .eq("id", qid)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_question_set(qid: str) -> Optional[dict]:
    resp = _client.table("question_sets").select("*").eq("id", qid).execute()
    return resp.data[0] if resp.data else None


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(host_name: str, question_set_id: str, password: str = "") -> dict:
    qs = get_question_set(question_set_id)
    if not qs:
        raise ValueError("Question set not found")

    # generate a unique code
    code = _make_code()
    while True:
        check = _client.table("sessions").select("id").eq("code", code).execute()
        if not check.data:
            break
        code = _make_code()

    session_row = {
        "code":            code,
        "host_name":       host_name,
        "question_set_id": question_set_id,
        "qs_title":        qs.get("title", "Untitled"),
        "password":        password,
        "status":          "waiting",
    }
    resp = _client.table("sessions").insert(session_row).execute()
    session = resp.data[0]

    # insert host as first player
    player_row = {
        "session_id":   session["id"],
        "display_name": host_name,
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


def join_session(code: str, player_name: str, password: str = "") -> tuple[dict, dict]:
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

    # check player count
    count_resp = (
        _client.table("session_players")
        .select("id", count="exact")
        .eq("session_id", sid)
        .execute()
    )
    if (count_resp.count or 0) >= MAX_PLAYERS:
        raise ValueError(f"Session full ({MAX_PLAYERS} players max)")

    # check name uniqueness
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
        "is_host":      False,
        "score":        0,
        "q_index":      0,
        "finished":     False,
    }
    p_resp = _client.table("session_players").insert(player_row).execute()
    p_data = p_resp.data[0]

    session_dict = _build_session_dict(session_row)

    player_dict = {
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
    # get session
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

    # get player
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

    # insert answer row
    answer_row = {
        "session_id":   sid,
        "player_id":    pid,
        "display_name": player_name,
        "q_index":      q_index,
        "chosen":       chosen,
        "correct":      correct,
        "got":          pts > 0,
        "pts":          pts,
        "time_taken":   round(time_taken, 2),
    }
    _client.table("answers").insert(answer_row).execute()

    # update player score and q_index
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

    # mark this player finished
    _client.table("session_players").update({"finished": True}).eq(
        "session_id", sid
    ).eq("display_name", player_name).execute()

    # check if all players are done
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

    # re-fetch to get updated status
    updated = _client.table("sessions").select("*").eq("id", sid).execute()
    return _build_session_dict(updated.data[0])