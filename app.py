"""
app.py
StudySquad home page.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.helpers import page_config, sidebar_identity, init_state, api_get
from components.auth import restore_session, get_current_user

page_config("StudySquad")
init_state()

# Redirect to auth if not logged in
if not restore_session() or not get_current_user():
    st.switch_page("pages/0_Auth.py")

sidebar_identity()

user        = get_current_user()
player_name = st.session_state.get("player_name", user["email"].split("@")[0] if user else "")

st.title(f"📚 Welcome back, {player_name}!")
st.markdown("Your AI-powered multiplayer study quiz platform.")
st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("### 📄 Upload Material")
    st.write("Add your study notes, textbook excerpts, or any content.")
    if st.button("Upload Material →", use_container_width=True):
        st.switch_page("pages/1_Upload_Material.py")

with col2:
    st.markdown("### 🤖 Generate Questions")
    st.write("Let AI create quiz questions from your material.")
    if st.button("Generate Questions →", use_container_width=True):
        st.switch_page("pages/2_Generate_Questions.py")

with col3:
    st.markdown("### 🎮 Play a Quiz")
    st.write("Host a session or join one with a code.")
    if st.button("Play Quiz →", use_container_width=True):
        st.switch_page("pages/4_Join_Session.py")

with col4:
    st.markdown("### 📊 My Dashboard")
    st.write("View your history, scores, and all your question sets.")
    if st.button("My Dashboard →", use_container_width=True):
        st.switch_page("pages/6_My_Dashboard.py")

st.divider()

# Quick stats from the user's history
data    = api_get("/me/history")
history = data.get("history", []) if data else []

if history:
    finished = [h for h in history if h["finished"]]
    avg_acc  = round(sum(h["accuracy"] for h in finished) / len(finished)) if finished else 0
    total_pts = sum(h["score"] for h in history)

    st.markdown("### Your Stats")
    c1, c2, c3 = st.columns(3)
    c1.metric("Sessions Played",    len(history))
    c2.metric("Average Accuracy",   f"{avg_acc}%")
    c3.metric("Total Points Earned", f"{total_pts} pts")
else:
    st.info("You haven't played any quizzes yet. Upload some material and get started!")

st.divider()
st.caption("StudySquad v1.0 · AI-powered by NVIDIA · Built with Streamlit + Supabase")
