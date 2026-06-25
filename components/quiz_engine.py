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

    if q_type in ["mcq", "truefalse"]:
        return user == correct, 1.0

    if q_type == "short":
        if user == correct:
            return True, 1.0

        # Word overlap: what fraction of correct answer words does the user cover
        correct_words = set(correct.split())
        user_words = set(user.split())
        if not correct_words:
            return False, 0.0

        overlap = len(correct_words & user_words) / len(correct_words)

        if overlap >= 0.8:
            return True, 1.0
        elif overlap >= 0.5:
            return True, 0.7
        elif overlap >= 0.3:
            return True, 0.4
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