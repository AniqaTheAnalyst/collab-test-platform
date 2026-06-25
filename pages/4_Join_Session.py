"""
pages/4_Join_Session.py
Join a session OR take a solo test. Contains the full quiz engine
with per-question countdown timer and live scoreboard.
"""

import time
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (page_config, sidebar_identity, init_state,
                            api_post, api_get, render_scoreboard, score_pts)

page_config("Quiz")
init_state()
sidebar_identity()


# ── Helper: load fresh session ─────────────────────────────────────────────────

def get_fresh_session(code: str):
    return api_get(f"/sessions/{code}")


# ── Quiz is active ─────────────────────────────────────────────────────────────

if st.session_state.get("quiz_active"):
    sess = st.session_state.get("session_data")
    if not sess:
        st.error("Session data lost.")
        st.session_state["quiz_active"] = False
        st.rerun()

    code = sess.get("code", "")
    player_name = st.session_state["player_name"]
    questions = sess.get("questions") or api_get(f"/question_sets/{sess['question_set_id']}").get("questions", [])
    time_limit = sess.get("time_limit", 15)
    q_index = st.session_state["q_index"]

    # ── All done ───────────────────────────────────────────────────────────────
    if q_index >= len(questions):
        if code:
            api_post("/sessions/finish", {"code": code, "player_name": player_name})
        st.session_state["quiz_active"] = False
        st.switch_page("pages/5_Results.py")
        st.stop()

    q = questions[q_index]

    # ── Header ─────────────────────────────────────────────────────────────────
    top_col1, top_col2, top_col3 = st.columns([3, 2, 1])
    with top_col1:
        progress = q_index / len(questions)
        st.progress(progress, text=f"Question {q_index+1} of {len(questions)}")
    with top_col2:
        if code:
            st.markdown(f"Session: **`{code}`**")
        st.markdown(f"Player: **{player_name}** | Score: **{st.session_state['score']}**")
    with top_col3:
        if st.button("🚪 Exit"):
            st.session_state["quiz_active"] = False
            st.session_state["q_index"] = 0
            st.rerun()

    st.divider()

    # ── Timer ──────────────────────────────────────────────────────────────────
    if st.session_state["q_start_time"] is None:
        st.session_state["q_start_time"] = time.time()

    elapsed = time.time() - st.session_state["q_start_time"]
    remaining = max(0.0, time_limit - elapsed)
    pct = remaining / time_limit

    if pct > 0.6:
        bar_color = "🟢"
        timer_color = "#1D9E75"
    elif pct > 0.3:
        bar_color = "🟡"
        timer_color = "#BA7517"
    else:
        bar_color = "🔴"
        timer_color = "#D85A30"

    timer_col, q_col = st.columns([1, 5])
    with timer_col:
        st.markdown(
            f"<div style='text-align:center;background:#f0f0f0;border-radius:50%;width:72px;height:72px;"
            f"display:flex;align-items:center;justify-content:center;margin:auto;"
            f"font-size:24px;font-weight:700;color:{timer_color}'>{int(remaining)}</div>",
            unsafe_allow_html=True
        )
        st.caption(f"{bar_color} Time left")

    with q_col:
        topic = q.get("topic_tag","")
        if topic:
            st.caption(f"Topic: `{topic}`")
        st.markdown(f"### {q['question']}")

    # ── Answer options ─────────────────────────────────────────────────────────
    answered_key = f"answered_{q_index}"
    already_answered = st.session_state.get(answered_key, False)

    st.write("DEBUG")
    st.write("q_index =", q_index)
    st.write("answered_key =", answered_key)
    st.write("already_answered =", already_answered)

    if remaining <= 0 and not already_answered:
        # Time's up — auto-submit blank
        st.session_state[answered_key] = True
        st.session_state[f"chosen_{q_index}"] = None
        pts = 0
        if code:
            api_post("/sessions/answer", {
                "code": code, "player_name": player_name,
                "q_index": q_index, "chosen": "", "correct": q["answer"],
                "pts": pts, "time_taken": time_limit,
            })
        st.session_state["answers"].append({
            "q_index": q_index, "question": q["question"],
            "chosen": None, "correct": q["answer"],
            "got": False, "pts": 0,
            "explanation": q.get("explanation",""),
        })
        st.warning("⏰ Time's up!")
        time.sleep(1.5)
        st.session_state["q_index"] += 1
        st.session_state["q_start_time"] = None
        st.rerun()

    if q.get("type") == "short":
        # Short answer
        if not already_answered:
            ans = st.text_input("Your answer:", key=f"short_{q_index}", placeholder="Type and press Enter")
            if st.button("Submit answer ✓", key=f"sub_{q_index}", type="primary"):
                time_taken = time.time() - st.session_state["q_start_time"]
                correct_ans = q["answer"]
                got = (ans.strip().lower() in correct_ans.lower() or
                       correct_ans.lower() in ans.strip().lower())
                pts = score_pts(time_limit, time_taken, got)
                st.session_state["score"] += pts
                st.session_state[answered_key] = True
                st.session_state[f"chosen_{q_index}"] = ans
                st.session_state["answers"].append({
                    "q_index": q_index, "question": q["question"],
                    "chosen": ans, "correct": correct_ans,
                    "got": got, "pts": pts,
                    "explanation": q.get("explanation",""),
                })
                if code:
                    api_post("/sessions/answer", {
                        "code": code, "player_name": player_name,
                        "q_index": q_index, "chosen": ans,
                        "correct": correct_ans, "pts": pts, "time_taken": time_taken,
                    })
                st.rerun()
        else:
            chosen = st.session_state.get(f"chosen_{q_index}")
            got = any(a.get("got") for a in st.session_state["answers"] if a.get("q_index")==q_index)
            if got:
                st.success(f"✅ Correct! You said: **{chosen}**")
            else:
                st.error(f"❌ Wrong. You said: **{chosen}** | Correct: **{q['answer']}**")
            if q.get("explanation"):
                st.info(f"💡 {q['explanation']}")
            if st.button("Next question →", type="primary"):
                st.session_state["q_index"] += 1
                st.session_state["q_start_time"] = None
                st.rerun()

    else:
        # MCQ / True-False
        options = q.get("options", [])
        if not already_answered:
            cols = st.columns(2) if len(options) == 4 else st.columns(len(options))
            for i, opt in enumerate(options):
                col = cols[i % len(cols)]
                with col:
                    if st.button(opt, key=f"opt_{q_index}_{i}", use_container_width=True):
                        time_taken = time.time() - st.session_state["q_start_time"]
                        correct_ans = q["answer"]
                        got = opt == correct_ans
                        pts = score_pts(time_limit, time_taken, got)
                        st.session_state["score"] += pts
                        st.session_state[answered_key] = True
                        st.session_state[f"chosen_{q_index}"] = opt
                        st.session_state["answers"].append({
                            "q_index": q_index, "question": q["question"],
                            "chosen": opt, "correct": correct_ans,
                            "got": got, "pts": pts,
                            "explanation": q.get("explanation",""),
                        })
                        if code:
                            api_post("/sessions/answer", {
                                "code": code, "player_name": player_name,
                                "q_index": q_index, "chosen": opt,
                                "correct": correct_ans, "pts": pts, "time_taken": time_taken,
                            })
                        st.rerun()
        else:
            chosen = st.session_state.get(f"chosen_{q_index}")
            got = any(a.get("got") for a in st.session_state["answers"] if a.get("q_index")==q_index)
            for opt in options:
                if opt == q["answer"] and got:
                    st.success(f"✅ {opt} ← Correct!")
                elif opt == chosen and not got:
                    st.error(f"❌ {opt} ← Your answer (wrong)")
                elif opt == q["answer"] and not got:
                    st.info(f"✅ {opt} ← Correct answer")
                else:
                    st.markdown(f"- {opt}")
            if q.get("explanation"):
                st.info(f"💡 {q['explanation']}")
            pts_got = next((a["pts"] for a in st.session_state["answers"] if a.get("q_index")==q_index), 0)
            if got:
                st.success(f"🎉 +{pts_got} points! (speed bonus included)")
            if st.button("Next question →", type="primary", use_container_width=True):
                st.session_state["q_index"] += 1
                st.session_state["q_start_time"] = None
                st.rerun()

    # ── Live scoreboard ────────────────────────────────────────────────────────
    if code:
        st.divider()
        st.markdown("#### 🏆 Live Scoreboard")
        fresh = get_fresh_session(code)
        if fresh:
            render_scoreboard(fresh.get("players", []))

    # Auto-refresh timer every second while unanswered
    if not already_answered:
        time.sleep(1)
        st.rerun()

    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# JOIN / SOLO PAGE (not in quiz yet)
# ─────────────────────────────────────────────────────────────────────────────

st.title("🚪 Join a Session or Take a Solo Test")

tab1, tab2 = st.tabs(["🔗 Join a Live Session", "🏃 Solo Test"])

# ── Tab 1: Join live session ──────────────────────────────────────────────────

with tab1:
    st.markdown("Enter the session code your friend shared with you.")

    col1, col2 = st.columns(2)
    with col1:
        join_name = st.text_input("Your name", value=st.session_state.get("player_name",""),
                                   placeholder="Your nickname", key="join_name_input")
        code_input = st.text_input("Session code", value=st.session_state.get("session_code",""),
                                    placeholder="e.g. ABCD-1234",
                                    key="join_code_input").upper().strip()
        join_pass = st.text_input("Password (if required)", type="password", key="join_pass")

        if st.button("🚀 Join Session", type="primary", use_container_width=True):
            if not join_name.strip():
                st.error("Enter your name")
            elif not code_input:
                st.error("Enter a session code")
            else:
                result = api_post("/sessions/join", {
                    "code": code_input,
                    "player_name": join_name.strip(),
                    "password": join_pass,
                })
                if result and result.get("success"):
                    sess = result["session"]
                    st.session_state["player_name"] = join_name.strip()
                    st.session_state["session_code"] = sess["code"]
                    st.session_state["is_host"] = False
                    st.session_state["session_data"] = sess
                    st.success(f"✅ Joined! Waiting for host to start…")
                    st.rerun()

    with col2:
        st.markdown("#### 🟢 Open Sessions")
        open_data = api_get("/sessions")
        if open_data and open_data.get("sessions"):
            for s in open_data["sessions"]:
                with st.container():
                    st.markdown(f"**`{s['code']}`** — {s['qs_title']}")
                    st.caption(f"Host: {s['host']} · {len(s['players'])}/5 players")
                    if st.button("Quick Join", key=f"qj_{s['code']}"):
                        st.session_state["session_code"] = s["code"]
                        st.rerun()
        else:
            st.info("No open sessions. Ask a friend to host one!")

    # Waiting room (if already joined but session not started)
    if st.session_state.get("session_code") and not st.session_state.get("is_host"):
        code = st.session_state["session_code"]
        sess = get_fresh_session(code)
        if sess:
            st.divider()
            if sess["status"] == "waiting":
                st.info(f"⏳ Waiting for host **{sess['host']}** to start the quiz…")
                st.markdown("**Players in lobby:**")
                for p in sess["players"]:
                    icon = "👑" if p.get("is_host") else "👤"
                    st.markdown(f"{icon} {p['name']}")
                time.sleep(2)
                st.rerun()
            elif sess["status"] == "started":
                st.success("🎉 Quiz started!")
                st.session_state["session_data"] = sess
                st.session_state["quiz_active"] = True
                st.session_state["q_index"] = 0
                st.session_state["answers"] = []
                st.session_state["score"] = 0
                st.session_state["q_start_time"] = None
                time.sleep(0.5)
                st.rerun()

# ── Tab 2: Solo test ──────────────────────────────────────────────────────────

with tab2:
    st.markdown("Take a timed test by yourself — no session code needed.")

    solo_name = st.text_input("Your name", value=st.session_state.get("player_name",""),
                               placeholder="Your name", key="solo_name_input")

    generated_qs = st.session_state.get("last_generated_qs")

    qs_data = api_get("/question_sets")
    qsets = qs_data.get("question_sets", []) if qs_data else []

    if generated_qs:
        qsets.insert(0, generated_qs)
    if not qsets:
        st.warning("No question sets saved. Generate some with AI first!")
        if st.button("🤖 Generate Questions"):
            st.switch_page("pages/2_Generate_Questions.py")
    else:
        options = {f"{qs['title']} — {len(qs.get('questions',[]))} Qs, {qs.get('time_limit',15)}s/q": qs
                   for qs in sorted(qsets, key=lambda x: x.get("created_at",""), reverse=True)}
        selected = st.selectbox("Choose question set", list(options.keys()), key="solo_qs_select")
        chosen_qs = options[selected]
    with st.expander("Quiz Information"):
        if "chosen_qs" in locals() and chosen_qs:
            st.write(f"Title: {chosen_qs['title']}")
        else:
            st.warning("No question set loaded. Please join session again.")
            st.stop()
        st.write(f"Questions: {len(chosen_qs.get('questions', []))}")
        st.write(f"Time per question: {chosen_qs.get('time_limit',15)} seconds")
        st.warning("Questions are hidden until the test begins.")

        col_a, col_b = st.columns(2)
        col_a.metric("Questions", len(chosen_qs.get("questions",[])))
        col_b.metric("Time/question", f"{chosen_qs.get('time_limit',15)}s")

        if st.button("▶ Start Solo Test", type="primary", use_container_width=True):
            if not solo_name.strip():
                st.error("Enter your name")
            else:

                # Clear previous quiz state
                for k in list(st.session_state.keys()):
                    if (
                        k.startswith("answered_")
                        or k.startswith("chosen_")
                        or k.startswith("short_")
                        or k.startswith("ai_exp_")
                    ):
                        del st.session_state[k]
                
                st.session_state["player_name"] = solo_name.strip()
                st.session_state["quiz_active"] = True
                st.session_state["session_code"] = ""
                st.session_state["is_host"] = False
                st.session_state["session_data"] = {
                    "code": "",
                    "time_limit": chosen_qs.get("time_limit", 15),
                    "questions": chosen_qs.get("questions", []),
                    "players": [{"name": solo_name.strip(), "score": 0, "is_host": False}],
                }
                st.session_state["q_index"] = 0
                st.session_state["answers"] = []
                st.session_state["score"] = 0
                st.session_state["q_start_time"] = None
                st.rerun()