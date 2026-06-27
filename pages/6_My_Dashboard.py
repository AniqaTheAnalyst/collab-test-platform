"""
pages/6_My_Dashboard.py
Personal dashboard — history, materials, question sets, all scoped to signed-in user.
"""

import streamlit as st
import sys, os
import streamlit as st

if st.session_state.get("sb_access_token"):
    st.warning("DEBUG TOKEN — remove this after testing")
    st.code(st.session_state["sb_access_token"])
    
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import page_config, sidebar_identity, init_state, api_get, api_post

page_config("My Dashboard")
init_state()
sidebar_identity()

# ── Auth guard ─────────────────────────────────────────────────────────────────
from components.auth import require_auth
user = require_auth()

player_name = st.session_state.get("player_name", user["email"].split("@")[0])

st.title(f"📊 {player_name}'s Dashboard")
st.caption(f"Signed in as {user['email']}")
st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_history, tab_materials, tab_qsets = st.tabs([
    "🏆 Quiz History", "📄 My Materials", "❓ My Question Sets"
])

# ── Quiz History ───────────────────────────────────────────────────────────────
with tab_history:
    st.markdown("### Sessions you've played")

    data = api_get("/me/history")
    history = data.get("history", []) if data else []

    if not history:
        st.info("No quiz history yet. Take a test to see your results here!")
        if st.button("🎮 Start a Quiz", type="primary"):
            st.switch_page("pages/4_Join_Session.py")
    else:
        # Summary metrics
        total_sessions   = len(history)
        finished_sessions = [h for h in history if h["session_status"] == "finished" or h["finished"]]
        avg_accuracy = (
            round(sum(h["accuracy"] for h in finished_sessions) / len(finished_sessions))
            if finished_sessions else 0
        )
        total_pts = sum(h["score"] for h in history)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sessions Played",   total_sessions)
        c2.metric("Sessions Finished", len(finished_sessions))
        c3.metric("Avg Accuracy",      f"{avg_accuracy}%")
        c4.metric("Total Points",      f"{total_pts} pts")

        st.divider()

        for h in history:
            icon   = "✅" if h["finished"] else "🔄"
            host   = "👑 Host" if h["is_host"] else "👤 Player"
            label  = f"{icon} {h['qs_title']} | {h['score']} pts | {h['accuracy']}% | {host}"

            with st.expander(label):
                col1, col2, col3 = st.columns(3)
                col1.metric("Score",    f"{h['score']} pts")
                col2.metric("Accuracy", f"{h['accuracy']}%")
                col3.metric("Correct",  f"{h['correct']}/{h['total_questions']}")

                if h.get("started_at"):
                    st.caption(f"Played: {h['started_at'][:10]}")
                if h.get("session_code"):
                    st.caption(f"Session code: {h['session_code']}")

                # Per-question breakdown
                if h["answers"]:
                    st.markdown("**Answer breakdown:**")
                    for a in h["answers"]:
                        got = a.get("got", False)
                        q_icon = "✅" if got else "❌"
                        st.markdown(
                            f"{q_icon} Q{a['q_index']+1} — "
                            f"Chose: `{a.get('chosen') or '(no answer)'}` | "
                            f"Correct: `{a.get('correct')}` | "
                            f"{a.get('pts', 0)} pts"
                        )

                # Retake this question set
                if h.get("question_set_id"):
                    if st.button("🔄 Retake this quiz", key=f"retake_{h['session_id']}"):
                        qs_data = api_get(f"/question_sets/{h['question_set_id']}")
                        if qs_data:
                            create_result = api_post("/sessions", {
                                "host_name":       player_name,
                                "question_set_id": h["question_set_id"],
                                "password":        "",
                            })
                            if create_result and create_result.get("success"):
                                sess = create_result["session"]
                                start_result = api_post("/sessions/start", {
                                    "code":      sess["code"],
                                    "host_name": player_name,
                                })
                                if start_result and start_result.get("success"):
                                    started = start_result["session"]
                                    started["questions"] = qs_data.get("questions", [])
                                    st.session_state["session_code"]  = started["code"]
                                    st.session_state["session_data"]  = started
                                    st.session_state["is_host"]       = True
                                    st.session_state["quiz_active"]   = True
                                    st.session_state["q_index"]       = 0
                                    st.session_state["answers"]       = []
                                    st.session_state["score"]         = 0
                                    st.session_state["q_start_time"]  = None
                                    st.switch_page("pages/4_Join_Session.py")


# ── My Materials ───────────────────────────────────────────────────────────────
with tab_materials:
    st.markdown("### Materials you've uploaded")

    data = api_get("/materials")
    materials = data.get("materials", []) if data else []

    if not materials:
        st.info("You haven't uploaded any study materials yet.")
        if st.button("📄 Upload Material", type="primary"):
            st.switch_page("pages/1_Upload_Material.py")
    else:
        st.caption(f"{len(materials)} material(s) saved")
        for m in materials:
            words = len(m.get("text", "").split())
            with st.expander(f"📄 {m['title']} — {words} words | {m.get('created_at', '')[:10]}"):
                if m.get("tags"):
                    st.caption(f"Tags: {m['tags']}")
                st.write(m["text"][:600] + ("…" if len(m.get("text", "")) > 600 else ""))

                if st.button("🤖 Generate questions from this", key=f"gen_{m['id']}"):
                    st.session_state["prefill_material"] = m["text"]
                    st.session_state["prefill_title"]    = m["title"]
                    st.switch_page("pages/2_Generate_Questions.py")


# ── My Question Sets ───────────────────────────────────────────────────────────
with tab_qsets:
    st.markdown("### Question sets you've generated")

    data = api_get("/question_sets")
    qsets = data.get("question_sets", []) if data else []

    if not qsets:
        st.info("No question sets yet. Generate some from your study materials!")
        if st.button("🤖 Generate Questions", type="primary"):
            st.switch_page("pages/2_Generate_Questions.py")
    else:
        st.caption(f"{len(qsets)} question set(s)")
        for qs in qsets:
            n_q   = len(qs.get("questions", []))
            label = f"❓ {qs['title']} — {n_q} questions | {qs.get('time_limit', 15)}s/q | {qs.get('created_at','')[:10]}"

            with st.expander(label):
                st.caption(f"Subject: {qs.get('subject', '')} | ID: {qs['id']}")
                pub_status = "🌐 Public" if qs.get("is_public") else "🔒 Private"
                st.caption(pub_status)

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button("👑 Host session", key=f"host_{qs['id']}"):
                        st.session_state["last_generated_qs"] = qs
                        st.switch_page("pages/3_Host_Session.py")

                with col_b:
                    if st.button("🏃 Solo test", key=f"solo_{qs['id']}"):
                        create_result = api_post("/sessions", {
                            "host_name":       player_name,
                            "question_set_id": qs["id"],
                            "password":        "",
                        })
                        if create_result and create_result.get("success"):
                            sess = create_result["session"]
                            start_result = api_post("/sessions/start", {
                                "code":      sess["code"],
                                "host_name": player_name,
                            })
                            if start_result and start_result.get("success"):
                                started = start_result["session"]
                                started["questions"] = qs.get("questions", [])
                                st.session_state["session_code"]  = started["code"]
                                st.session_state["session_data"]  = started
                                st.session_state["is_host"]       = True
                                st.session_state["quiz_active"]   = True
                                st.session_state["q_index"]       = 0
                                st.session_state["answers"]       = []
                                st.session_state["score"]         = 0
                                st.session_state["q_start_time"]  = None
                                st.switch_page("pages/4_Join_Session.py")

                with col_c:
                    if not qs.get("is_public"):
                        if st.button("🌐 Publish", key=f"pub_{qs['id']}"):
                            api_post(f"/question_sets/{qs['id']}/publish", {})
                            st.rerun()
