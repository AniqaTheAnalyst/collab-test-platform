"""
pages/1_Upload_Material.py
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import page_config, sidebar_identity, init_state, api_post, api_get

page_config("Upload Material")
init_state()
sidebar_identity()

st.title("📄 Upload Study Material")
st.markdown("Paste notes, textbook excerpts, or any content you want to study. Any team member can be the uploader.")

st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    uploader = st.text_input("Your name (who's uploading)", value=st.session_state.get("player_name", ""),
                              placeholder="e.g. Rafi")
    title = st.text_input("Topic / Subject title", placeholder="e.g. Photosynthesis, Chapter 5: Cell Division")
    text = st.text_area("Study content", height=300,
                         placeholder="Paste your lecture notes, textbook paragraphs, definitions, key points...\n\nTip: More detailed material = better AI questions!")
    tags = st.text_input("Tags (optional, comma-separated)", placeholder="biology, midterm, chapter-3")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Save Material", type="primary", use_container_width=True):
            if not uploader.strip():
                st.error("Enter your name")
            elif not title.strip():
                st.error("Enter a topic title")
            elif not text.strip():
                st.error("Paste some content")
            elif len(text.strip()) < 50:
                st.warning("Add more content for better AI questions (at least a paragraph)")
            else:
                with st.spinner("Saving..."):
                    result = api_post("/materials", {
                        "title": title.strip(),
                        "text": text.strip(),
                        "uploader": uploader.strip(),
                        "tags": tags.strip(),
                    })
                if result and result.get("success"):
                    st.success(f"✅ Material saved! You can now generate questions from it.")
                    st.session_state["player_name"] = uploader.strip()
                    if st.button("→ Generate Questions from this"):
                        st.switch_page("pages/2_Generate_Questions.py")

    with col_btn2:
        if st.button("🤖 Generate Questions →", use_container_width=True):
            st.switch_page("pages/2_Generate_Questions.py")

with col2:
    st.markdown("#### 📋 Tips for good material")
    st.info("""
**What works well:**
- Lecture notes with key points
- Textbook paragraphs
- Definitions and explanations
- Lists of facts or concepts
- Any structured text

**Ideal length:**
- 200–2000 words
- More content = more variety in questions

**Supported formats:**
- Plain text (paste directly)
- Bullet points
- Numbered lists
- Mixed content
    """)

    st.markdown("#### 📊 Material stats")
    if text:
        words = len(text.split())
        chars = len(text)
        st.metric("Words", words)
        st.metric("Characters", chars)
        est_q = min(20, max(3, words // 50))
        st.metric("Estimated max questions", est_q)

st.divider()
st.markdown("### 📚 All Saved Materials")

data = api_get("/materials")
if data and data.get("materials"):
    mats = sorted(data["materials"], key=lambda m: m.get("created_at", ""), reverse=True)
    for m in mats:
        with st.expander(f"**{m['title']}** — uploaded by {m['uploader']} | {len(m['text'].split())} words"):
            if m.get("tags"):
                st.caption(f"Tags: {m['tags']}")
            st.write(m["text"][:500] + ("…" if len(m["text"]) > 500 else ""))
else:
    st.info("No materials saved yet.")