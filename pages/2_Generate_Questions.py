"""
pages/2_Generate_Questions.py
Core AI question generation page with full prompt customisation.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import (page_config, sidebar_identity, init_state,
                            api_post, api_get, PROVIDER_MODELS)

page_config("Generate Questions")
init_state()
sidebar_identity()

st.title("🤖 Generate Questions with AI")
st.markdown("Configure exactly how you want your questions — type, difficulty, tone — and write custom prompts for precise control.")

st.divider()

# ── Source material ────────────────────────────────────────────────────────────

st.markdown("### 1️⃣ Choose Study Material")
source_tab1, source_tab2 = st.tabs(["📂 From saved materials", "✏️ Paste custom text"])

material_text = ""

with source_tab1:
    data = api_get("/materials")
    materials = data.get("materials", []) if data else []
    if materials:
        options = {f"{m['title']} (by {m['uploader']})": m for m in materials}
        selected_label = st.selectbox("Select material", ["— choose —"] + list(options.keys()))
        if selected_label != "— choose —":
            mat = options[selected_label]
            material_text = mat["text"]
            st.success(f"✅ Loaded: **{mat['title']}** — {len(material_text.split())} words")
            with st.expander("Preview material"):
                st.write(material_text[:600] + "…")
    else:
        st.warning("No saved materials. Upload some first or use the paste tab.")

with source_tab2:
    custom_text = st.text_area("Paste any content here", height=200,
                                placeholder="Paste notes, paragraphs, definitions...")
    if custom_text.strip():
        material_text = custom_text.strip()

st.divider()

# ── AI Configuration ───────────────────────────────────────────────────────────

st.markdown("### 2️⃣ Configure AI Generation")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Question Settings")

    q_type = st.radio("Question type", [
        "mcq", "truefalse", "short", "mixed"
    ], format_func=lambda x: {
        "mcq": "🔤 Multiple Choice (4 options)",
        "truefalse": "✅ True / False",
        "short": "✏️ Short Answer",
        "mixed": "🎲 Mixed (all types)",
    }[x], horizontal=False)

    difficulty = st.select_slider("Difficulty", ["easy", "medium", "hard"],
                                   value="medium",
                                   format_func=lambda x: x.capitalize())

    num_questions = st.slider("Number of questions", 3, 20, 5, 1)

    time_limit = st.slider("Time limit per question (seconds)", 5, 60, 15, 5,
                            help="How long each player has to answer")

with col2:
    st.markdown("#### Style & Focus")

    tone = st.selectbox("Question tone / style", [
        "academic", "casual", "challenging"
    ], format_func=lambda x: {
        "academic": "🎓 Academic (formal textbook style)",
        "casual": "💬 Casual (friendly, conversational)",
        "challenging": "🔥 Challenging (tricky distractors, edge cases)",
    }[x])

    focus_area = st.text_input("Focus area (optional)",
                                placeholder="e.g. Only questions about mitosis, not meiosis")

    temperature = st.slider("AI creativity", 0.0, 1.0, 0.4, 0.05,
                             help="Lower = more precise/predictable, Higher = more creative/varied")

    provider = "NVIDIA"
    model = "meta/llama-3.1-8b-instruct"
    st.info(f"Using: **{provider}** / `{model}`")

st.divider()

# ── Custom Prompt Engineering ──────────────────────────────────────────────────

st.markdown("### 3️⃣ Custom Prompt (Prompt Engineering)")
st.markdown("Write any extra instructions to guide the AI. This is appended directly to the LangChain prompt.")

custom_prompt = st.text_area(
    "Your custom instructions",
    height=120,
    placeholder="""Examples:
- "Focus on definitions and terminology only"
- "Make sure all MCQ options are similar in length (no giveaways)"  
- "Include at least 2 questions about the causes, not just effects"
- "Write questions a 10-year-old could understand"
- "All questions must have a clear single correct answer, no ambiguity"
- "Avoid questions that can be answered by common knowledge alone"
"""
)

with st.expander("💡 Prompt engineering tips"):
    st.markdown("""
**Control question style:**
- "Use Bloom's taxonomy — focus on analysis and evaluation, not just recall"
- "All questions must start with 'Which of the following...'"
- "Write questions in Bengali / Spanish / French"

**Control content:**
- "Only ask about the first half of the material"
- "Include at least one question per paragraph"
- "Avoid any questions about dates or names"

**Control difficulty:**  
- "Distractors must be plausible — no obviously wrong answers"
- "Include at least 2 questions that require combining two facts"
- "Make the correct answer always be option B or C (for testing purposes)"
""")

st.divider()

# ── Generate button ────────────────────────────────────────────────────────────
st.markdown("### 4️⃣ Generate!")

uploader_name = st.session_state.get("player_name", "")

generate_clicked = st.button(
    "✨ Generate Questions with AI",
    type="primary",
    use_container_width=True,
    disabled=not material_text
)

if not material_text:
    st.warning("⬆️ Select or paste material above to enable generation")
if generate_clicked and material_text:
    with st.spinner(f"🤖 {provider} is generating {num_questions} {q_type} questions…"):
        result = api_post("/generate", {
            "material": material_text,
            "num_questions": num_questions,
            "question_type": q_type,
            "difficulty": difficulty,
            "time_limit": time_limit,
            "focus_area": focus_area,
            "tone": tone,
            "custom_prompt": custom_prompt,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "save": True,
            "uploader": uploader_name,
        })

    if result and result.get("success"):
        qs = result["question_set"]
        st.session_state["last_generated_qs"] = qs
        st.session_state["active_question_set_id"] = qs["id"]

# ── Show last generated ────────────────────────────────────────────────────────
qs = st.session_state.get("last_generated_qs")

if qs:
    st.success(f"✅ Generated {len(qs.get('questions', []))} questions successfully.")
    st.info(f"Quiz Title: {qs.get('title', 'Untitled Quiz')}")
    # FIX: removed duplicate warning; one clear message is enough
    st.warning("Questions are hidden until the quiz starts.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("👑 Host Session", use_container_width=True):
            st.switch_page("pages/3_Host_Session.py")


    with col2:
        if st.button("🏃 Solo Test", use_container_width=True):
            player_name = st.session_state.get("player_name", "").strip()
            if not player_name:
                st.error("Enter your name in the sidebar before starting a solo test.")
            else:
                with st.spinner("Starting solo session…"):
                    # Create a session for this player
                    create_result = api_post("/sessions", {
                        "host_name": player_name,
                        "question_set_id": qs["id"],
                        "password": "",
                    })
                    if create_result and create_result.get("success"):
                        sess = create_result["session"]
                        # Start it immediately (no waiting for others)
                        start_result = api_post("/sessions/start", {
                            "code": sess["code"],
                            "host_name": player_name,
                        })
                        if start_result and start_result.get("success"):
                            started_sess = start_result["session"]
                            started_sess["questions"] = qs.get("questions", [])
                            st.session_state["session_code"] = started_sess["code"]
                            st.session_state["session_data"] = started_sess
                            st.session_state["is_host"] = True
                            st.session_state["quiz_active"] = True
                            st.session_state["q_index"] = 0
                            st.session_state["answers"] = []
                            st.session_state["score"] = 0
                            st.session_state["q_start_time"] = None
                            st.switch_page("pages/4_Join_Session.py")

    with col3:
        if st.button("🗑️ Discard", use_container_width=True):
            st.session_state["last_generated_qs"] = None
            st.rerun()

# ── Saved question sets ────────────────────────────────────────────────────────

st.markdown("### 📚 All Saved Question Sets")
data = api_get("/question_sets")
if data and data.get("question_sets"):
    for qs_item in sorted(data["question_sets"], key=lambda x: x.get("created_at",""), reverse=True):
        label = f"**{qs_item['title']}** — {len(qs_item.get('questions',[]))} questions | {qs_item.get('time_limit',15)}s/q"
        with st.expander(label):
            st.caption(f"Subject: {qs_item.get('subject','')} | ID: {qs_item.get('id','')}")
            st.caption(f"{len(qs_item.get('questions', []))} questions hidden until the quiz is completed.")
else:
    st.info("No question sets saved yet.")