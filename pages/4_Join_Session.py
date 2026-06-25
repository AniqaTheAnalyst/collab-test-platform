"""
pages/4_Join_Session.py
Clean UI quiz engine (NO logic duplication)
"""

import time
import streamlit as st
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (
    page_config, sidebar_identity, init_state,
    api_post, api_get
)

from components.quiz_engine import evaluate, score_pts

page_config("Quiz")
init_state()
sidebar_identity()


# ── SESSION LOADER ────────────────────────────────────────────────
def get_session():
    return st.session_state.get("session_data")


# ── MAIN QUIZ FLOW ────────────────────────────────────────────────
if st.session_state.get("quiz_active"):

    sess = get_session()

    if not sess:
        st.error("Session lost")
        st.stop()

    code = sess.get("code", "")
    player_name = st.session_state["player_name"]

    # FIX: api_get can return None (API offline); guard before calling .get()
    questions = sess.get("questions") or []
    if not questions:
        qs_data = api_get(f"/question_sets/{sess['question_set_id']}")
        if qs_data is None:
            st.error("❌ Could not load questions — API is unreachable.")
            st.stop()
        questions = qs_data.get("questions", [])

    time_limit = sess.get("time_limit", 15)
    q_index = st.session_state["q_index"]

    # ── FINISH ────────────────────────────────────────────────
    if q_index >= len(questions):
        if code:
            api_post("/sessions/finish", {
                "code": code,
                "player_name": player_name
            })

        st.session_state["quiz_active"] = False
        st.switch_page("pages/5_Results.py")
        st.stop()

    q = questions[q_index]

    # ── TIMER ────────────────────────────────────────────────
    if st.session_state["q_start_time"] is None:
        st.session_state["q_start_time"] = time.time()

    elapsed = time.time() - st.session_state["q_start_time"]
    remaining = max(0, time_limit - elapsed)

    answered_key = f"answered_{q_index}"
    already_answered = st.session_state.get(answered_key, False)

    # ── TIMEOUT ────────────────────────────────────────────────
    if remaining <= 0 and not already_answered:

        st.session_state[answered_key] = True

        st.session_state["answers"].append({
            "q_index": q_index,
            "question": q["question"],
            "chosen": None,
            "correct": q["answer"],
            "got": False,
            "confidence": 0.0,
            "pts": 0,
            "explanation": q.get("explanation", "")
        })

        if code:
            api_post("/sessions/answer", {
                "code": code,
                "player_name": player_name,
                "q_index": q_index,
                "chosen": "",
                "correct": q["answer"],
                "pts": 0,
                "time_taken": time_limit,
            })

        st.warning("⏰ Time's up!")
        time.sleep(1)

        st.session_state["q_index"] += 1
        st.session_state["q_start_time"] = None
        st.rerun()

    # ── SHORT ANSWER ────────────────────────────────────────────────
    if q.get("type") == "short":

        if not already_answered:

            ans = st.text_input("Your answer:", key=f"short_{q_index}")

            if st.button("Submit", key=f"sub_{q_index}"):

                time_taken = time.time() - st.session_state["q_start_time"]

                got, confidence = evaluate("short", ans, q["answer"])

                pts = score_pts(time_limit, time_taken, got, confidence)

                st.session_state["score"] += pts
                st.session_state[answered_key] = True
                st.session_state[f"chosen_{q_index}"] = ans

                st.session_state["answers"].append({
                    "q_index": q_index,
                    "question": q["question"],
                    "chosen": ans,
                    "correct": q["answer"],
                    "got": got,
                    "confidence": confidence,
                    "pts": pts,
                    "explanation": q.get("explanation", "")
                })

                if code:
                    api_post("/sessions/answer", {
                        "code": code,
                        "player_name": player_name,
                        "q_index": q_index,
                        "chosen": ans,
                        "correct": q["answer"],
                        "pts": pts,
                        "time_taken": time_taken,
                    })

                st.rerun()

        else:

            chosen = st.session_state.get(f"chosen_{q_index}")

            got = any(
                a.get("got") for a in st.session_state["answers"]
                if a["q_index"] == q_index
            )

            if got:
                st.success(f"✅ Correct: {chosen}")
            else:
                st.error(f"❌ Wrong: {chosen}")

            if q.get("explanation"):
                st.info(q["explanation"])

            if st.button("Next →"):
                st.session_state["q_index"] += 1
                st.session_state["q_start_time"] = None
                st.rerun()

    # ── MCQ / TRUE FALSE ────────────────────────────────────────────────
    else:

        options = q.get("options", [])

        if not already_answered:

            cols = st.columns(min(len(options), 4))

            for i, opt in enumerate(options):

                with cols[i % len(cols)]:

                    if st.button(opt, key=f"opt_{q_index}_{i}"):

                        time_taken = time.time() - st.session_state["q_start_time"]

                        got, confidence = evaluate(q.get("type", "mcq"), opt, q["answer"])

                        pts = score_pts(time_limit, time_taken, got, confidence)

                        st.session_state["score"] += pts
                        st.session_state[answered_key] = True
                        st.session_state[f"chosen_{q_index}"] = opt

                        st.session_state["answers"].append({
                            "q_index": q_index,
                            "question": q["question"],
                            "chosen": opt,
                            "correct": q["answer"],
                            "got": got,
                            "confidence": confidence,
                            "pts": pts,
                            "explanation": q.get("explanation", "")
                        })

                        if code:
                            api_post("/sessions/answer", {
                                "code": code,
                                "player_name": player_name,
                                "q_index": q_index,
                                "chosen": opt,
                                "correct": q["answer"],
                                "pts": pts,
                                "time_taken": time_taken,
                            })

                        st.rerun()

        else:

            chosen = st.session_state.get(f"chosen_{q_index}")

            got = any(
                a.get("got") for a in st.session_state["answers"]
                if a["q_index"] == q_index
            )

            for opt in options:
                if opt == q["answer"] and got:
                    st.success(f"✅ {opt}")
                elif opt == chosen and not got:
                    st.error(f"❌ {opt}")
                elif opt == q["answer"]:
                    st.info(f"✔ {opt}")
                else:
                    st.write(opt)

            if q.get("explanation"):
                st.info(q["explanation"])

            if st.button("Next →", use_container_width=True):
                st.session_state["q_index"] += 1
                st.session_state["q_start_time"] = None
                st.rerun()

    st.stop()