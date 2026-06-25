"""
app.py — StudySquad Home Page
Run: streamlit run app.py
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.helpers import page_config, sidebar_identity, init_state, api_get

page_config("StudySquad — Home")
init_state()
sidebar_identity()

# ── Hero ───────────────────────────────────────────────────────────────────────

st.markdown("""
<h1 style='font-size:2.2rem;font-weight:700;margin-bottom:0'>
📚 StudySquad
</h1>
<p style='font-size:1.1rem;color:#666;margin-top:4px'>
AI-powered multiplayer quiz platform — upload material, generate questions, test your squad.
</p>
""", unsafe_allow_html=True)

st.divider()

# ── Quick nav cards ────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("### 📄 Upload")
    st.markdown("Paste notes or study material. One of your friends can be the content creator.")
    if st.button("Upload Material →", use_container_width=True):
        st.switch_page("pages/1_Upload_Material.py")

with col2:
    st.markdown("### 🤖 Generate")
    st.markdown("Use AI to generate custom questions — choose type, difficulty, and write your own prompt.")
    if st.button("Generate Questions →", use_container_width=True):
        st.switch_page("pages/2_Generate_Questions.py")

with col3:
    st.markdown("### 👑 Host")
    st.markdown("Create a live session with a shareable code. Up to 5 players can join.")
    if st.button("Host a Session →", use_container_width=True):
        st.switch_page("pages/3_Host_Session.py")

with col4:
    st.markdown("### 🚪 Join")
    st.markdown("Enter a code to join a friend's session, or take a solo timed test.")
    if st.button("Join / Solo Test →", use_container_width=True):
        st.switch_page("pages/4_Join_Session.py")

st.divider()

# ── Recent materials ───────────────────────────────────────────────────────────

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("### 📂 Recent Materials")
    data = api_get("/materials")
    if data and data.get("materials"):
        mats = sorted(data["materials"], key=lambda m: m.get("created_at", ""), reverse=True)[:5]
        for m in mats:
            with st.expander(f"**{m['title']}** — by {m['uploader']}"):
                st.caption(m.get("tags", ""))
                st.write(m["text"][:300] + ("…" if len(m["text"]) > 300 else ""))
    else:
        st.info("No materials yet. Upload some to get started!")

with col_b:
    st.markdown("### 🎯 Saved Question Sets")
    data = api_get("/question_sets")
    if data and data.get("question_sets"):
        sets = sorted(data["question_sets"], key=lambda q: q.get("created_at",""), reverse=True)[:5]
        for qs in sets:
            with st.expander(f"**{qs['title']}** — {len(qs.get('questions',[]))} questions"):
                st.caption(f"Subject: {qs.get('subject','')} | Time: {qs.get('time_limit',15)}s/q")
                for q in qs.get("questions", [])[:3]:
                    st.markdown(f"- {q['question'][:80]}…")
    else:
        st.info("No question sets yet. Generate some with AI!")

st.divider()

# ── Open sessions ──────────────────────────────────────────────────────────────

st.markdown("### 🟢 Live Open Sessions")
data = api_get("/sessions")
if data and data.get("sessions"):
    for s in data["sessions"]:
        c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
        with c1:
            st.markdown(f"**`{s['code']}`**")
        with c2:
            st.markdown(f"{s['qs_title']} · Host: {s['host']}")
        with c3:
            st.markdown(f"👥 {len(s['players'])}/5 players")
        with c4:
            if st.button("Join", key=f"join_{s['code']}"):
                st.session_state["session_code"] = s["code"]
                st.switch_page("pages/4_Join_Session.py")
else:
    st.info("No open sessions. Host one!")

st.divider()
st.caption("StudySquad v1.0 · Built with Streamlit + FastAPI + LangChain · Supports OpenAI, Anthropic, Google Gemini")