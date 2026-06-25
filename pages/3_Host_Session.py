"""
pages/3_Host_Session.py
Create and manage a live quiz session (up to 5 players).
"""

import time
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (page_config, sidebar_identity, init_state,
                            api_post, api_get, render_scoreboard)

page_config("Host Session")
init_state()
sidebar_identity()

st.title("👑 Host a Quiz Session")
st.markdown("Create a live session. Share the code with up to 4 friends (5 players total).")

st.divider()

# ── Session is already created ─────────────────────────────────────────────────

if st.session_state.get("session_code") and st.session_state.get("is_host"):
    code = st.session_state["session_code"]
    sess = api_get(f"/sessions/{code}")

    if not sess:
        st.error("Session not found. It may have expired.")
        st.session_state["session_code"] = ""
        st.session_state["is_host"] = False
        st.rerun()

    # ── Waiting lobby ──────────────────────────────────────────────────────────
    if sess["status"] == "waiting":
        st.markdown(f"## 🔑 Session Code: `{sess['code']}`")
        st.markdown("Share this code with your friends so they can join.")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("### 👥 Players in lobby")
            for p in sess["players"]:
                icon = "👑" if p.get("is_host") else "👤"
                st.markdown(f"{icon} **{p['name']}**")
            st.caption(f"{len(sess['players'])}/5 players")

            if len(sess["players"]) >= 2:
                if st.button("🚀 Start Quiz Now!", type="primary", use_container_width=True):
                    result = api_post("/sessions/start", {
                        "code": code,
                        "host_name": st.session_state["player_name"],
                    })
                    if result and result.get("success"):
                        st.session_state["session_data"] = result["session"]
                        st.session_state["quiz_active"] = True
                        st.session_state["q_index"] = 0
                        st.session_state["answers"] = []
                        st.session_state["score"] = 0
                        st.switch_page("pages/4_Join_Session.py")
            else:
                st.info("Waiting for at least 1 more player to join…")
                if st.button("▶ Start solo anyway"):
                    result = api_post("/sessions/start", {
                        "code": code,
                        "host_name": st.session_state["player_name"],
                    })
                    if result and result.get("success"):
                        st.session_state["session_data"] = result["session"]
                        st.session_state["quiz_active"] = True
                        st.session_state["q_index"] = 0
                        st.session_state["answers"] = []
                        st.session_state["score"] = 0
                        st.switch_page("pages/4_Join_Session.py")

        with col2:
            st.markdown("### 📋 Quiz Information")

            qs_id = sess.get("question_set_id")
            if qs_id:
                qs = api_get(f"/question_sets/{qs_id}")
                if qs:
                    st.markdown(f"**{qs.get('title')}**")
                    st.caption(
                        f"{len(qs.get('questions',[]))} questions · "
                        f"{qs.get('time_limit',15)}s per question"
                    )
                    st.warning("Questions are hidden until the quiz starts.")

        st.divider()
        if st.button("↩ Leave / Cancel session"):
            st.session_state["session_code"] = ""
            st.session_state["is_host"] = False
            st.rerun()

        # Auto-refresh for player join updates
        time.sleep(2)
        st.rerun()

    elif sess["status"] in ("started", "finished"):
        st.info("Session is running or finished. Go to Join/Quiz page.")
        if st.button("→ Go to Quiz"):
            st.switch_page("pages/4_Join_Session.py")

    st.stop()

# ── Create new session ─────────────────────────────────────────────────────────

st.markdown("### Step 1: Your identity")
host_name = st.text_input("Your name (host)", value=st.session_state.get("player_name", ""),
                           placeholder="Your name")

st.markdown("### Step 2: Pick question set")

generated_qs = st.session_state.get("last_generated_qs")

qs_data = api_get("/question_sets")
saved_sets = qs_data.get("question_sets", []) if qs_data else []

# FIX: deduplicate — if last_generated_qs is already in saved_sets (post-publish),
# don't add it a second time.
saved_ids = {qs["id"] for qs in saved_sets}
question_sets = []
if generated_qs and generated_qs.get("id") not in saved_ids:
    question_sets.append(generated_qs)
question_sets.extend(saved_sets)

if not question_sets:
    st.warning("No question sets saved. Generate some first!")
    if st.button("🤖 Go to Generate Questions"):
        st.switch_page("pages/2_Generate_Questions.py")
else:
    options = {f"{qs['title']} — {len(qs.get('questions',[]))} Qs, {qs.get('time_limit',15)}s/q": qs
               for qs in sorted(question_sets, key=lambda x: x.get("created_at",""), reverse=True)}
    selected_label = st.selectbox("Question set", list(options.keys()))
    chosen_qs = options[selected_label]

    # FIX: chosen_qs is always defined here (inside the else block), so the
    # redundant `if "chosen_qs" in locals()` guard is removed.
    with st.expander("Quiz information"):
        st.write(f"Title: {chosen_qs['title']}")
        st.write(f"Questions: {len(chosen_qs.get('questions', []))}")
        st.write(f"Time per question: {chosen_qs.get('time_limit',15)} seconds")
        st.warning("Questions are hidden until the quiz is completed.")

    st.markdown("### Step 3: Session settings")
    password = st.text_input("Session password (optional — leave blank for open)", type="password")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"⏱ **{chosen_qs.get('time_limit',15)} seconds** per question (set when generating)")
        st.info(f"👥 **Up to 5 players** can join")

    st.divider()
    if st.button("🚀 Create Session", type="primary", use_container_width=True):
        if not host_name.strip():
            st.error("Enter your name")
        else:
            result = api_post("/sessions", {
                "host_name": host_name.strip(),
                "question_set_id": chosen_qs["id"],
                "password": password,
            })
            if result and result.get("success"):
                sess = result["session"]
                st.session_state["session_code"] = sess["code"]
                st.session_state["player_name"] = host_name.strip()
                st.session_state["is_host"] = True
                st.session_state["session_data"] = sess
                st.success(f"✅ Session created! Code: **{sess['code']}**")
                st.rerun()