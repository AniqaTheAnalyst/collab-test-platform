"""
components/session_store.py
Thread-safe in-memory session manager with JSON file persistence.
Supports up to 5 concurrent players per session.
"""

import json
import os
import random
import string
import threading
import time
from datetime import datetime
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
MATERIALS_FILE = os.path.join(DATA_DIR, "materials.json")
QSETS_FILE = os.path.join(DATA_DIR, "question_sets.json")

_lock = threading.Lock()

MAX_PLAYERS = 5


# ── File helpers ──────────────────────────────────────────────────────────────

def _load(path: str) -> dict | list:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Code generator ────────────────────────────────────────────────────────────

def _make_code() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=4))
    digits = "".join(random.choices(string.digits, k=4))
    return f"{letters}-{digits}"


# ── Materials ─────────────────────────────────────────────────────────────────

def save_material(title: str, text: str, uploader: str, tags: str = "") -> dict:
    with _lock:
        materials = _load(MATERIALS_FILE) or {}
        mid = str(int(time.time() * 1000))
        materials[mid] = {
            "id": mid,
            "title": title,
            "text": text,
            "uploader": uploader,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
        }
        _save(MATERIALS_FILE, materials)
        return materials[mid]


def get_all_materials() -> list:
    return list((_load(MATERIALS_FILE) or {}).values())


def get_material(mid: str) -> Optional[dict]:
    return (_load(MATERIALS_FILE) or {}).get(mid)


# ── Question sets ─────────────────────────────────────────────────────────────

def save_question_set(qs: dict, uploader: str = "") -> dict:
    with _lock:
        sets = _load(QSETS_FILE) or {}
        qid = str(int(time.time() * 1000))
        qs["id"] = qid
        qs["uploader"] = uploader
        qs["created_at"] = datetime.now().isoformat()
        qs["is_public"] = False
        sets[qid] = qs
        _save(QSETS_FILE, sets)
        return qs


def get_all_question_sets() -> list:
    return [qs for qs in ((_load(QSETS_FILE) or {}).values()) if qs.get("is_public", False)]


def publish_question_set(qid: str) -> Optional[dict]:
    with _lock:
        sets = _load(QSETS_FILE) or {}
        qs = sets.get(qid)
        if not qs:
            return None
        qs["is_public"] = True
        sets[qid] = qs
        _save(QSETS_FILE, sets)
        return qs


def get_question_set(qid: str) -> Optional[dict]:
    return (_load(QSETS_FILE) or {}).get(qid)


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(host_name: str, question_set_id: str, password: str = "") -> dict:
    with _lock:
        sessions = _load(SESSIONS_FILE) or {}
        qs = get_question_set(question_set_id)
        if not qs:
            raise ValueError("Question set not found")
        code = _make_code()
        while code in [s["code"] for s in sessions.values()]:
            code = _make_code()
        sid = str(int(time.time() * 1000))
        session = {
            "id": sid,
            "code": code,
            "host": host_name,
            "question_set_id": question_set_id,
            "qs_title": qs.get("title", "Untitled"),
            "time_limit": qs.get("time_limit", 15),
            "password": password,
            "status": "waiting",   # waiting | started | finished
            "players": [
                {
                    "name": host_name,
                    "is_host": True,
                    "score": 0,
                    "q_index": 0,
                    "answers": [],
                    "finished": False,
                    "joined_at": datetime.now().isoformat(),
                }
            ],
            "current_question": 0,
            "created_at": datetime.now().isoformat(),
        }
        sessions[sid] = session
        _save(SESSIONS_FILE, sessions)
        return session


def get_session_by_code(code: str) -> Optional[dict]:
    sessions = _load(SESSIONS_FILE) or {}
    for s in sessions.values():
        if s["code"] == code.upper().strip():
            return s
    return None


def get_session(sid: str) -> Optional[dict]:
    return (_load(SESSIONS_FILE) or {}).get(sid)


def get_open_sessions() -> list:
    sessions = _load(SESSIONS_FILE) or {}
    return [s for s in sessions.values() if s["status"] == "waiting"]


def join_session(code: str, player_name: str, password: str = "") -> tuple[dict, dict]:
    with _lock:
        sessions = _load(SESSIONS_FILE) or {}
        target = None
        sid = None
        for k, s in sessions.items():
            if s["code"] == code.upper().strip():
                target = s
                sid = k
                break
        if not target:
            raise ValueError("Session not found")
        if target["status"] != "waiting":
            raise ValueError("Session already started or finished")
        if len(target["players"]) >= MAX_PLAYERS:
            raise ValueError(f"Session full ({MAX_PLAYERS} players max)")
        if target["password"] and target["password"] != password:
            raise ValueError("Wrong password")
        if any(p["name"] == player_name for p in target["players"]):
            raise ValueError("Name already taken in this session")
        player = {
            "name": player_name,
            "is_host": False,
            "score": 0,
            "q_index": 0,
            "answers": [],
            "finished": False,
            "joined_at": datetime.now().isoformat(),
        }
        target["players"].append(player)
        sessions[sid] = target
        _save(SESSIONS_FILE, sessions)
        return target, player


def start_session(code: str, host_name: str) -> dict:
    with _lock:
        sessions = _load(SESSIONS_FILE) or {}
        for sid, s in sessions.items():
            if s["code"] == code and s["host"] == host_name:
                s["status"] = "started"
                s["started_at"] = datetime.now().isoformat()
                sessions[sid] = s
                _save(SESSIONS_FILE, sessions)
                return s
        raise ValueError("Session not found or not host")


def submit_answer(code: str, player_name: str, q_index: int,
                  chosen: str, correct: str, pts: int, time_taken: float) -> dict:
    with _lock:
        sessions = _load(SESSIONS_FILE) or {}
        for sid, s in sessions.items():
            if s["code"] == code:
                for p in s["players"]:
                    if p["name"] == player_name:
                        p["score"] += pts
                        p["q_index"] = q_index + 1
                        p["answers"].append({
                            "q_index": q_index,
                            "chosen": chosen,
                            "correct": correct,
                            "got": chosen == correct,
                            "pts": pts,
                            "time_taken": round(time_taken, 2),
                        })
                sessions[sid] = s
                _save(SESSIONS_FILE, sessions)
                return s
        raise ValueError("Session not found")


def finish_player(code: str, player_name: str) -> dict:
    with _lock:
        sessions = _load(SESSIONS_FILE) or {}
        for sid, s in sessions.items():
            if s["code"] == code:
                for p in s["players"]:
                    if p["name"] == player_name:
                        p["finished"] = True
                if all(p["finished"] for p in s["players"]):
                    s["status"] = "finished"
                sessions[sid] = s
                _save(SESSIONS_FILE, sessions)
                return s
        raise ValueError("Session not found")