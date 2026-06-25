"""
components/quiz_engine.py
Central quiz logic (evaluation + scoring engine)
"""

def normalize(text):
    if text is None:
        return ""
    return str(text).strip().lower()


# ── EVALUATION ENGINE ──────────────────────────────────────────────
def evaluate(q_type: str, user: str, correct: str):
    user = normalize(user)
    correct = normalize(correct)

    # MCQ / TRUE FALSE
    if q_type in ["mcq", "truefalse"]:
        return user == correct, 1.0

    # SHORT ANSWER (partial credit)
    if q_type == "short":
        if user == correct:
            return True, 1.0
        elif user in correct or correct in user:
            return True, 0.7
        else:
            return False, 0.0

    return False, 0.0


# ── SCORING ENGINE ────────────────────────────────────────────────
def score_pts(time_limit: int, time_taken: float, correct: bool, confidence: float = 1.0):
    """
    Final scoring:
    - base = 100
    - speed bonus = up to +50
    - multiplied by confidence (only meaningful for short answers)
    """

    if not correct:
        return 0

    base = 100
    speed_bonus = max(0, int((1 - time_taken / time_limit) * 50))

    return int((base + speed_bonus) * confidence)