"""
utils/helpers.py
Shared utilities, API client, and UI helpers for Streamlit pages.
All API calls now inject the user's JWT token as a Bearer header.
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

API_URL = os.getenv("API_URL", "https://collab-test-platform.onrender.com")

PROVIDER_MODELS = {
    "NVIDIA": [
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.3-70b-instruct",
    ],
}

AVATAR_COLORS = [
    ("#6C63FF", "#EEF0FF"),
    ("#1D9E75", "#E1F5EE"),
    ("#D85A30", "#FAECE7"),
    ("#BA7517", "#FAEEDA"),
    ("#378ADD", "#E6F1FB"),
]


# ── Auth helpers (imported here so pages only need one import) ─────────────────

from components.auth import require_auth, get_current_user, get_access_token, sign_out


def get_user_id(name: str = "") -> str:
    """Return authenticated user's ID. Falls back to lowercased name for legacy."""
    user = get_current_user()
    if user:
        return user["id"]
    return (name or "").lower().strip()


def _auth_headers() -> dict:
    """Return Authorization header dict with current user's JWT, if logged in."""
    token = get_access_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── API wrappers ───────────────────────────────────────────────────────────────

def api_get(endpoint: str, params=None):
    try:
        r = requests.get(
            f"{API_URL}{endpoint}",
            params=params,
            headers=_auth_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to API server.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(endpoint: str, data: dict):
    try:
        r = requests.post(
            f"{API_URL}{endpoint}",
            json=data,
            headers=_auth_headers(),
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to API server.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ── Session state helpers ──────────────────────────────────────────────────────

def init_state():
    defaults = {
        "player_name": "",
        "session_code": "",
        "session_data": None,
        "is_host": False,
        "quiz_active": False,
        "q_index": 0,
        "answers": [],
        "score": 0,
        "q_start_time": None,
        "selected_provider": "NVIDIA",
        "selected_model": "meta/llama-3.1-8b-instruct",
        "last_generated_qs": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Auto-populate player_name from auth if not set
    if not st.session_state.get("player_name"):
        user = get_current_user()
        if user:
            # Use display name from pending signup or fall back to email prefix
            display = st.session_state.pop("pending_display_name", None)
            if not display:
                display = user["email"].split("@")[0]
            st.session_state["player_name"] = display


# ── UI helpers ─────────────────────────────────────────────────────────────────

def page_config(title: str = "StudySquad"):
    st.set_page_config(
        page_title=title,
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def sidebar_identity():
    user = get_current_user()
    with st.sidebar:
        st.markdown("## 📚 StudySquad")
        st.divider()

        if user:
            # Show authenticated user info
            st.markdown(f"👤 **{st.session_state.get('player_name', user['email'])}**")
            st.caption(user["email"])
            name = st.text_input(
                "Display name",
                value=st.session_state.get("player_name", ""),
                key="sidebar_name",
            )
            if name:
                st.session_state["player_name"] = name

            if st.button("Sign Out", use_container_width=True):
                sign_out()
                st.switch_page("pages/0_Auth.py")
        else:
            st.warning("Not signed in")
            if st.button("Sign In", use_container_width=True):
                st.switch_page("pages/0_Auth.py")

        st.divider()
        st.markdown("#### 🤖 AI Settings")
        st.caption("Using NVIDIA for AI generation.")
        st.session_state["selected_provider"] = "NVIDIA"
        st.session_state["selected_model"] = "meta/llama-3.1-8b-instruct"

        st.divider()
        st.caption(f"API: {API_URL}")
        try:
            r = requests.get(f"{API_URL}/health", timeout=2)
            if r.status_code == 200:
                st.success("API ✅ Online")
            else:
                st.warning("API ⚠️ Degraded")
        except Exception:
            st.error("API ❌ Offline")


def score_pts(time_limit: int, time_taken: float, correct: bool, confidence: float = 1.0) -> int:
    from components.quiz_engine import score_pts as _score_pts
    return _score_pts(time_limit, time_taken, correct, confidence)


def render_scoreboard(players: list):
    if not players:
        return
    sorted_p = sorted(players, key=lambda p: p.get("score", 0), reverse=True)
    for i, p in enumerate(sorted_p):
        color, bg = AVATAR_COLORS[i % len(AVATAR_COLORS)]
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        col1, col2, col3 = st.columns([1, 5, 2])
        with col1:
            st.markdown(f"<span style='font-size:20px'>{medal}</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(
                f"<div style='background:{bg};padding:6px 12px;border-radius:8px;"
                f"color:{color};font-weight:500'>{p['name']}"
                f"{'&nbsp;👑 Host' if p.get('is_host') else ''}</div>",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(f"**{p.get('score', 0)} pts**")
