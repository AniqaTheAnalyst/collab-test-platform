"""
pages/5_Results.py
Post-quiz results: score, leaderboard, answer review, AI explanations.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (page_config, sidebar_identity, init_state,
                            api_post, api_get, render_scoreboard, API_URL)

page_config("Results")
init_state()
sidebar_identity()

answers = st.session_state.get("answers", [])
score = st.session_state.get("score", 0)
player_name = st.session_state.get("player_name", "You")
code = st.session_state.get("session_code", "")
provider = "NVIDIA"
model = "meta/llama-3.1-8b-instruct"

if not answers:
    st.title("📊 Results")
    st.info("No quiz data found. Take a test first!")
    if st.button("→ Take a test"):
        st.switch_page("pages/4_Join_Session.py")
    st.stop()

# ── Score summary ──────────────────────────────────────────────────────────────
total = len(answers)
correct = sum(1 for a in answers if a.get("got"))
accuracy = round((correct / total) * 100) if total else 0

if accuracy >= 80:
    grade, emoji = "Excellent", "🏆"
elif accuracy >= 60:
    grade, emoji = "Good", "🌟"
elif accuracy >= 40:
    grade, emoji = "Fair", "📈"
else:
    grade, emoji = "Keep practicing", "💪"

# Silently publish question set
qset_id = st.session_state.get("active_question_set_id") or (
    st.session_state.get("session_data") or {}
).get("question_set_id")

if qset_id:
    try:
        import requests as _requests
        _requests.post(f"{API_URL}/question_sets/{qset_id}/publish", timeout=5)
    except Exception:
        pass

st.title(f"{emoji} {grade}, {player_name}!")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Score", f"{score} pts")
col2.metric("Correct", f"{correct}/{total}")
col3.metric("Accuracy", f"{accuracy}%")
col4.metric("Wrong", f"{total - correct}/{total}")
st.progress(accuracy / 100, text=f"{accuracy}% accuracy")
st.divider()

# ── Leaderboard — only for multiplayer sessions, silently skip if gone ─────────
if code:
    try:
        import requests as _requests
        r = _requests.get(f"{API_URL}/sessions/{code}", timeout=5)
        if r.status_code == 200:
            sess = r.json()
            players = sess.get("players", [])
            if len(players) > 1:  # only show leaderboard for multiplayer
                st.markdown("### 🏆 Final Leaderboard")
                render_scoreboard(players)
                st.divider()
    except Exception:
        pass

# ── Answer review ──────────────────────────────────────────────────────────────
st.markdown("### 📋 Answer Review")

for a in answers:
    got = a.get("got", False)
    icon = "✅" if got else "❌"
    pts = a.get("pts", 0)

    with st.expander(f"{icon} Q{a['q_index']+1}: {a['question'][:80]}{'…' if len(a['question'])>80 else ''} | {pts} pts"):
        st.markdown(f"**Question:** {a['question']}")
        chosen = a.get("chosen")
        correct_ans = a.get("correct")

        if chosen:
            if got:
                st.success(f"✅ Your answer: **{chosen}** (correct!)")
            else:
                st.error(f"❌ Your answer: **{chosen}**")
                st.info(f"✅ Correct answer: **{correct_ans}**")
        else:
            st.warning("⏰ No answer submitted (time ran out)")
            st.info(f"✅ Correct answer: **{correct_ans}**")

        if a.get("explanation"):
            st.markdown(f"*{a.get('explanation')}*")

        if not got:
            exp_key = f"ai_exp_{a['q_index']}"
            if exp_key not in st.session_state:
                if st.button(f"🤖 Get AI explanation", key=f"btn_exp_{a['q_index']}"):
                    with st.spinner("Thinking…"):
                        result = api_post("/explain", {
                            "question": a["question"],
                            "correct_answer": correct_ans or "",
                            "student_answer": chosen or "(no answer)",
                            "context": "",
                            "provider": provider,
                            "model": model,
                        })
                    if result:
                        st.session_state[exp_key] = result.get("explanation", "")
                        st.rerun()
            else:
                st.markdown("**AI Explanation:**")
                st.markdown(st.session_state[exp_key])

st.divider()

# ── Actions ────────────────────────────────────────────────────────────────────
st.markdown("### What next?")
col_a, col_b, col_c = st.columns(3)

with col_a:
    if st.button("🔄 Retake this test", use_container_width=True, type="primary"):
        st.session_state["quiz_active"] = True
        st.session_state["q_index"] = 0
        st.session_state["answers"] = []
        st.session_state["score"] = 0
        st.session_state["q_start_time"] = None
        keys_to_del = [k for k in st.session_state if k.startswith("answered_") or
                       k.startswith("chosen_") or k.startswith("ai_exp_") or
                       k.startswith("timed_out_")]
        for k in keys_to_del:
            del st.session_state[k]
        st.switch_page("pages/4_Join_Session.py")

with col_b:
    if st.button("🤖 Generate new questions", use_container_width=True):
        st.switch_page("pages/2_Generate_Questions.py")

with col_c:
    if st.button("🏠 Home", use_container_width=True):
        st.session_state["quiz_active"] = False
        st.session_state["session_code"] = ""
        st.session_state["is_host"] = False
        st.switch_page("app.py")

st.divider()
st.caption("StudySquad v1.0 · AI-powered by NVIDIA")