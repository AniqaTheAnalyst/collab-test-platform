"""
components/auth.py
Supabase Auth wrapper — sign up, sign in, sign out, session management.
All other components import get_current_user() to get the authenticated user.
"""

import os
from typing import Optional
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")

_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# ── Session helpers ───────────────────────────────────────────────────────────

def _save_session(session_obj) -> None:
    """Persist Supabase session into Streamlit session_state."""
    st.session_state["sb_access_token"] = session_obj.access_token
    st.session_state["sb_refresh_token"] = session_obj.refresh_token
    st.session_state["sb_user_id"] = session_obj.user.id
    st.session_state["sb_user_email"] = session_obj.user.email


def _clear_session() -> None:
    for key in ["sb_access_token", "sb_refresh_token", "sb_user_id", "sb_user_email"]:
        st.session_state.pop(key, None)


# ── Public API ────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    """
    Register a new user.
    Returns {"success": True, "user": ...} or {"success": False, "error": str}.
    """
    try:
        res = _client.auth.sign_up({"email": email, "password": password})
        if res.user:
            return {"success": True, "user": res.user, "needs_confirmation": not res.session}
        return {"success": False, "error": "Sign-up failed — no user returned."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_in(email: str, password: str) -> dict:
    """
    Sign in an existing user.
    Returns {"success": True} or {"success": False, "error": str}.
    """
    try:
        res = _client.auth.sign_in_with_password({"email": email, "password": password})
        if res.session:
            _save_session(res.session)
            return {"success": True}
        return {"success": False, "error": "Invalid credentials."}
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg:
            return {"success": False, "error": "Wrong email or password."}
        return {"success": False, "error": msg}


def sign_out() -> None:
    """Sign out the current user and clear session."""
    try:
        _client.auth.sign_out()
    except Exception:
        pass
    _clear_session()
    # Also clear quiz state
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)


def restore_session() -> bool:
    """
    Try to restore a session from refresh token stored in session_state.
    Call this at the top of every page before require_auth().
    Returns True if a valid session is now active.
    """
    # Already have a valid token in memory
    if st.session_state.get("sb_access_token") and st.session_state.get("sb_user_id"):
        return True

    # Try to refresh using stored refresh token
    refresh_token = st.session_state.get("sb_refresh_token")
    if refresh_token:
        try:
            res = _client.auth.refresh_session(refresh_token)
            if res.session:
                _save_session(res.session)
                return True
        except Exception:
            pass

    _clear_session()
    return False


def get_current_user() -> Optional[dict]:
    """
    Returns {"id": str, "email": str} if logged in, else None.
    """
    if not st.session_state.get("sb_user_id"):
        return None
    return {
        "id": st.session_state["sb_user_id"],
        "email": st.session_state.get("sb_user_email", ""),
    }


def get_access_token() -> Optional[str]:
    """Return the current JWT access token, or None if not logged in."""
    return st.session_state.get("sb_access_token")


def require_auth() -> dict:
    """
    Call at the top of any page that requires login.
    If not logged in, shows a redirect message and stops execution.
    Returns the current user dict if authenticated.
    """
    if not restore_session():
        st.warning("🔒 Please sign in to access this page.")
        if st.button("→ Go to Sign In"):
            st.switch_page("pages/0_Auth.py")
        st.stop()
    user = get_current_user()
    if not user:
        st.switch_page("pages/0_Auth.py")
        st.stop()
    return user
