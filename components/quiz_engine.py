"""
components/quiz_engine.py
Central quiz logic — AI-powered evaluation + scoring engine.
"""

import os
import requests


def normalize(text):
    if text is None:
        return ""
    return str(text).strip().lower()


def _api_url() -> str:
    # FIX 4: read at call time, not import time, so load_dotenv() has already
    # been called by the Streamlit page before this is ever executed.
    return os.getenv("API_URL", "https://collab-test-platform.onrender.com")


# ── AI EVALUATION ──────────────────────────────────────────────────────────────
def evaluate(q_type: str, user: str, correct: str, question: str = "") -> tuple:
    user_n = normalize(user)
    correct_n = normalize(correct)

    # Fast path: exact match — no need to call AI
    if user_n == correct_n:
        return True, 1.0

    try:
        resp = requests.post(
            f"{_api_url()}/evaluate",
            json={
                "question": question,
                "correct_answer": correct,
                "student_answer": user,
                "q_type": q_type,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        correct_flag = bool(data.get("correct", False))
        confidence = float(data.get("confidence", 1.0 if correct_flag else 0.0))
        return correct_flag, confidence
    except Exception:
        # Fallback: exact match only
        match = user_n == correct_n
        return match, 1.0 if match else 0.0


# ── SCORING ENGINE ─────────────────────────────────────────────────────────────
def score_pts(time_limit: int, time_taken: float, correct: bool, confidence: float = 1.0) -> int:
    if not correct:
        return 0
    base = 100
    speed_bonus = max(0, int((1 - time_taken / time_limit) * 50))
    return int((base + speed_bonus) * confidence)