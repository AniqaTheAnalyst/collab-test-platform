"""
pages/0_Auth.py
Login and sign-up page for StudySquad.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from components.auth import sign_in, sign_up, get_current_user, restore_session

st.set_page_config(
    page_title="StudySquad — Sign In",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# If already logged in, redirect home
if restore_session() and get_current_user():
    st.switch_page("app.py")

# ── Page styles ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="collapsedControl"] { display: none; }
.auth-header { text-align: center; padding: 2rem 0 1rem; }
.auth-header h1 { font-size: 2.5rem; margin-bottom: 0.25rem; }
.auth-header p  { color: #888; font-size: 1rem; }
.stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 2rem; }
.stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="auth-header">
    <h1>📚 StudySquad</h1>
    <p>AI-powered multiplayer study quizzes</p>
</div>
""", unsafe_allow_html=True)

st.divider()

tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

# ── Sign In ───────────────────────────────────────────────────────────────────
with tab_login:
    st.markdown("### Welcome back")
    email_in = st.text_input("Email", placeholder="you@example.com", key="login_email")
    pass_in  = st.text_input("Password", type="password", key="login_pass")

    if st.button("Sign In", type="primary", use_container_width=True):
        if not email_in.strip():
            st.error("Enter your email.")
        elif not pass_in:
            st.error("Enter your password.")
        else:
            with st.spinner("Signing in…"):
                result = sign_in(email_in.strip().lower(), pass_in)
            if result["success"]:
                st.success("✅ Signed in!")
                st.switch_page("app.py")
            else:
                st.error(result["error"])

# ── Sign Up ───────────────────────────────────────────────────────────────────
with tab_signup:
    st.markdown("### Create your account")
    email_up   = st.text_input("Email", placeholder="you@example.com", key="signup_email")
    pass_up    = st.text_input("Password (min 6 chars)", type="password", key="signup_pass")
    pass_up2   = st.text_input("Confirm password", type="password", key="signup_pass2")
    display_up = st.text_input("Display name", placeholder="e.g. Aniqa", key="signup_name")

    if st.button("Create Account", type="primary", use_container_width=True):
        if not email_up.strip():
            st.error("Enter your email.")
        elif len(pass_up) < 6:
            st.error("Password must be at least 6 characters.")
        elif pass_up != pass_up2:
            st.error("Passwords don't match.")
        elif not display_up.strip():
            st.error("Enter a display name.")
        else:
            with st.spinner("Creating account…"):
                result = sign_up(email_up.strip().lower(), pass_up)
            if result["success"]:
                # Store display name in session for later use
                st.session_state["pending_display_name"] = display_up.strip()
                if result.get("needs_confirmation"):
                    st.success("✅ Account created! Check your email to confirm, then sign in.")
                else:
                    # Auto-signed in (email confirmation disabled in Supabase)
                    st.success("✅ Account created! Signing you in…")
                    login_result = sign_in(email_up.strip().lower(), pass_up)
                    if login_result["success"]:
                        st.switch_page("app.py")
            else:
                st.error(result["error"])

st.divider()
st.caption("Your data is private. Only you can see your materials, questions, and results.")
