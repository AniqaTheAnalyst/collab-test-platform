"""
pages/1_Upload_Material.py
Supports plain text paste, PDF upload, and image upload (OCR).
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cv2
import numpy as np

from utils.helpers import page_config, sidebar_identity, init_state, api_post, api_get
from components.auth import require_auth

page_config("Upload Material")
init_state()
sidebar_identity()

user = require_auth()

st.title("📄 Upload Study Material")
st.markdown("Upload a PDF, image, or paste text directly. Materials are private to your account.")
st.divider()

# ── File text extraction helpers ───────────────────────────────────────────────

def extract_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if text:
                pages_text.append(f"[Page {page_num + 1}]\n{text}")
        doc.close()
        return "\n\n".join(pages_text)
    except ImportError:
        st.error("PyMuPDF not installed. Run: pip install pymupdf")
        return ""
    except Exception as e:
        st.error(f"PDF extraction error: {e}")
        return ""

def preprocess_image(file_bytes: bytes) -> bytes:
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return file_bytes

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Resize DOWN if image is very large (vision models don't need >1600px wide)
    h, w = gray.shape
    max_dim = 1600
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # Light threshold instead of equalizeHist — faster and cleaner for text
    _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    success, buffer = cv2.imencode(".png", gray, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not success:
        return file_bytes

    return buffer.tobytes()


def _is_repetitive(text: str, threshold: float = 0.4) -> bool:
    """Return True if the text seems to be a hallucination loop."""
    if not text or len(text) < 100:
        return False
    chunks = [text[i:i+80] for i in range(0, len(text), 80)]
    unique_ratio = len(set(chunks)) / len(chunks)
    return unique_ratio < threshold


def extract_from_image(file_bytes: bytes, filename: str) -> str:
    """Extract text from an image using NVIDIA API (free tier)."""
    try:
        import base64
        from openai import OpenAI

        ext = filename.lower().split(".")[-1]
        media_type_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif", "webp": "image/webp",
        }
        media_type = media_type_map.get(ext, "image/jpeg")

        processed = preprocess_image(file_bytes)
        b64_image = base64.standard_b64encode(processed).decode("utf-8")
        image_url = f"data:{media_type};base64,{b64_image}"

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY"),
        )

        response = client.chat.completions.create(
            model="meta/llama-3.2-11b-vision-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {
                            "type": "text",
                            "text": (
                                "You are an OCR engine. Transcribe ONLY the text visible in this image.\n"
                                "Rules:\n"
                                "- Copy text exactly as written (Bangla or English).\n"
                                "- Preserve line breaks and numbering.\n"
                                "- Write [UNCLEAR] for unreadable words.\n"
                                "- Do NOT translate, summarize, explain, or add anything.\n"
                                "- Do NOT repeat lines.\n"
                                "- Stop after the last visible line.\n"
                                "Output the transcription only."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=2048,
            temperature=0.0,
            stop=["[END]", "---"],
        )

        result = response.choices[0].message.content.strip()

        if _is_repetitive(result):
            st.warning("⚠️ The model produced repetitive output. The image may be too complex or low-contrast. Try cropping it into smaller sections.")
            return ""

        return result

    except Exception as e:
        st.error(f"Image extraction error: {e}")
        return ""


# ── Layout ─────────────────────────────────────────────────────────────────────

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 1️⃣ Choose input method")
    input_tab1, input_tab2, input_tab3 = st.tabs(["✏️ Paste Text", "📑 Upload PDF", "🖼️ Upload Image"])

    extracted_text = ""
    extracted_title = ""

    # ── Tab 1: Paste text ──────────────────────────────────────────────────────
    with input_tab1:
        pasted = st.text_area(
            "Paste your study content here",
            height=280,
            placeholder="Paste lecture notes, textbook paragraphs, definitions, key points…\n\nTip: More detailed material = better AI questions!",
        )
        if pasted.strip():
            extracted_text = pasted.strip()

    # ── Tab 2: PDF upload ──────────────────────────────────────────────────────
    with input_tab2:
        pdf_file = st.file_uploader(
            "Upload a PDF file",
            type=["pdf"],
            help="Text-based PDFs work best. Scanned PDFs may have lower accuracy.",
        )
        if pdf_file:
            with st.spinner("Extracting text from PDF…"):
                raw = extract_from_pdf(pdf_file.read())
            if raw:
                st.success(f"✅ Extracted {len(raw.split())} words from {pdf_file.name}")
                with st.expander("Preview extracted text"):
                    st.text(raw[:1000] + ("…" if len(raw) > 1000 else ""))
                extracted_text  = raw
                extracted_title = os.path.splitext(pdf_file.name)[0].replace("_", " ").replace("-", " ").title()
            else:
                st.warning("No text could be extracted. Try a text-based PDF or paste the content manually.")

    # ── Tab 3: Image upload ────────────────────────────────────────────────────
    with input_tab3:
        img_file = st.file_uploader(
            "Upload an image of your notes",
            type=["png", "jpg", "jpeg", "webp"],
            help="Handwritten notes, whiteboard photos, textbook page photos, or screenshots.",
        )

        # Clear stale session state when a new image is uploaded
        if img_file:
            current_name = img_file.name
            if st.session_state.get("_last_img_name") != current_name:
                st.session_state.pop("img_extracted_text", None)
                st.session_state.pop("img_extracted_title", None)
                st.session_state["_last_img_name"] = current_name

            st.image(img_file, caption="Uploaded image", use_container_width=True)
            if st.button("🔍 Extract Text from Image", type="primary"):
                with st.spinner("Reading text from image…"):
                    img_file.seek(0)
                    raw = extract_from_image(img_file.read(), img_file.name)
                if raw:
                    st.session_state["img_extracted_text"]  = raw
                    st.session_state["img_extracted_title"] = os.path.splitext(img_file.name)[0].replace("_", " ").title()
                    st.success(f"✅ Extracted {len(raw.split())} words from image")
                else:
                    st.warning("Could not extract text. Try a clearer image.")

        if st.session_state.get("img_extracted_text"):
            with st.expander("Preview extracted text"):
                st.text(st.session_state["img_extracted_text"][:1000] + "…")
            extracted_text  = st.session_state["img_extracted_text"]
            extracted_title = st.session_state.get("img_extracted_title", "")

    # ── Save form (outside tabs, inside col1) ──────────────────────────────────
    st.divider()
    st.markdown("### 2️⃣ Save Material")

    title = st.text_input(
        "Topic / Subject title",
        value=extracted_title,
        placeholder="e.g. Photosynthesis, Chapter 5: Cell Division",
    )
    tags = st.text_input(
        "Tags (optional, comma-separated)",
        placeholder="biology, midterm, chapter-3",
    )

    if extracted_text:
        st.caption(f"📝 Ready to save: {len(extracted_text.split())} words")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Save Material", type="primary", use_container_width=True):
            if not title.strip():
                st.error("Enter a topic title")
            elif not extracted_text.strip():
                st.error("Add content first — paste text or upload a file above")
            elif len(extracted_text.strip()) < 50:
                st.warning("Add more content for better AI questions (at least a paragraph)")
            else:
                with st.spinner("Saving…"):
                    result = api_post("/materials", {
                        "title": title.strip(),
                        "text":  extracted_text.strip(),
                        "tags":  tags.strip(),
                    })
                if result and result.get("success"):
                    st.success("✅ Material saved!")
                    st.session_state.pop("img_extracted_text", None)
                    st.session_state.pop("img_extracted_title", None)
                    st.session_state.pop("_last_img_name", None)

    with col_btn2:
        if st.button("🤖 Generate Questions →", use_container_width=True, disabled=not extracted_text):
            if extracted_text:
                st.session_state["prefill_material"] = extracted_text
                st.session_state["prefill_title"]    = title.strip()
            st.switch_page("pages/2_Generate_Questions.py")

# ── Right column ───────────────────────────────────────────────────────────────
with col2:
    st.markdown("#### 📋 Supported formats")
    st.info("""
**✏️ Paste Text**
- Lecture notes
- Textbook excerpts
- Definitions & key points
- Any structured text

**📑 PDF Upload**
- Text-based PDFs ✅
- Lecture slides (PDF) ✅
- Scanned PDFs ⚠️ lower accuracy

**🖼️ Image Upload**
- Handwritten notes
- Whiteboard photos
- Textbook page photos
- Screenshots of slides

**Ideal content length:**
- 200–2000 words
- More = more question variety
    """)

    st.markdown("#### 📊 Content stats")
    if extracted_text:
        words = len(extracted_text.split())
        chars = len(extracted_text)
        st.metric("Words", words)
        st.metric("Characters", chars)
        est_q = min(20, max(3, words // 50))
        st.metric("Estimated max questions", est_q)
        if words < 100:
            st.warning("Short content — try adding more for better questions")
        elif words > 1500:
            st.info("Long content — AI will sample the most important parts")

# ── Saved materials list ───────────────────────────────────────────────────────
st.divider()
st.markdown("### 📚 Your Saved Materials")

data = api_get("/materials")
if data and data.get("materials"):
    mats = sorted(data["materials"], key=lambda m: m.get("created_at", ""), reverse=True)
    st.caption(f"{len(mats)} material(s) saved")
    for m in mats:
        words = len(m.get("text", "").split())
        with st.expander(f"📄 {m['title']} | {words} words | {m.get('created_at', '')[:10]}"):
            if m.get("tags"):
                st.caption(f"Tags: {m['tags']}")
            st.write(m["text"][:500] + ("…" if len(m.get("text", "")) > 500 else ""))
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🤖 Generate questions", key=f"gen_{m['id']}"):
                    st.session_state["prefill_material"] = m["text"]
                    st.session_state["prefill_title"]    = m["title"]
                    st.switch_page("pages/2_Generate_Questions.py")
else:
    st.info("No materials saved yet. Upload something above!")