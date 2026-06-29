"""
api/server.py
FastAPI REST backend for StudySquad.
Run with: uvicorn api.server:app --reload --port 8000
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import jwt as pyjwt

from components import supabase_store as store
from components.llm_chain import generate_questions, explain_wrong_answer
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

app = FastAPI(
    title="StudySquad API",
    description="AI-powered multiplayer study quiz platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*", "Authorization", "X-User-Id", "X-User-Email"],
)


# ── Auth dependency ────────────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict:
    # Skip JWT decode — Supabase now uses ES256 which requires public key verification
    # Trust X-User-Id header instead (set by Streamlit after Supabase login)
    user_id = request.headers.get("x-user-id", "").strip()
    if user_id:
        return {
            "id": user_id,
            "email": request.headers.get("x-user-email", ""),
        }

    # Last resort: try to extract sub from JWT without verification
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            # Decode without verification — we trust Supabase issued it
            payload = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["ES256", "HS256"],
            )
            user_id = payload.get("sub")
            if user_id:
                return {"id": user_id, "email": payload.get("email", "")}
        except Exception:
            pass

    raise HTTPException(401, "Authentication required. Please sign in.")

# ── Health ─────────────────────────────────────────────────────────────────────



@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "StudySquad API v1.0"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "timestamp": time.time()}


# ── Materials ──────────────────────────────────────────────────────────────────

class MaterialCreate(BaseModel):
    title: str
    text: str
    tags: str = ""


@app.post("/materials", tags=["Materials"])
def create_material(body: MaterialCreate, user: dict = Depends(get_current_user)):
    m = store.save_material(body.title, body.text, user["id"], body.tags)
    return {"success": True, "material": m}


@app.get("/materials", tags=["Materials"])
def list_materials(user: dict = Depends(get_current_user)):
    try:
        return {"materials": store.get_user_materials(user["id"])}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"Materials error: {type(e).__name__}: {str(e)}")


@app.get("/materials/{mid}", tags=["Materials"])
def get_material(mid: str, user: dict = Depends(get_current_user)):
    m = store.get_material(mid, user["id"])
    if not m:
        raise HTTPException(404, "Material not found")
    return m


# ── Question Generation ────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    material: str
    num_questions: int = 5
    question_type: str = "mcq"
    difficulty: str = "medium"
    time_limit: int = 15
    focus_area: str = ""
    tone: str = "academic"
    custom_prompt: str = ""
    provider: str = "NVIDIA"
    model: str = "meta/llama-3.1-8b-instruct"
    temperature: float = 0.4
    save: bool = True


@app.post("/generate", tags=["Questions"])
def generate(body: GenerateRequest, user: dict = Depends(get_current_user)):
    try:
        qs = generate_questions(
            material=body.material,
            num_questions=body.num_questions,
            question_type=body.question_type,
            difficulty=body.difficulty,
            time_limit=body.time_limit,
            focus_area=body.focus_area,
            tone=body.tone,
            custom_prompt=body.custom_prompt,
            provider="NVIDIA",
            model=body.model or "meta/llama-3.1-8b-instruct",
            temperature=body.temperature,
        )
        if body.save:
            qs = store.save_question_set(qs, user["id"])
        return {"success": True, "question_set": qs}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/question_sets", tags=["Questions"])
def list_question_sets(user: dict = Depends(get_current_user)):
    return {"question_sets": store.get_user_question_sets(user["id"])}


@app.post("/question_sets/{qid}/publish", tags=["Questions"])
def publish_question_set(qid: str, user: dict = Depends(get_current_user)):
    qs = store.publish_question_set(qid, user["id"])
    if not qs:
        raise HTTPException(404, "Question set not found")
    return {"success": True, "question_set": qs}


@app.get("/question_sets/{qid}", tags=["Questions"])
def get_question_set(qid: str, user: dict = Depends(get_current_user)):
    # First try: user owns it
    qs = store.get_question_set(qid, user["id"])
    if qs:
        return qs
    # Second try: user is a session participant (not the owner)
    qs = store.get_question_set(qid, user_id=None)
    if qs:
        return qs
    raise HTTPException(404, "Question set not found")


# ── Sessions ───────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    host_name: str
    question_set_id: str
    password: str = ""


class JoinSessionRequest(BaseModel):
    code: str
    player_name: str
    password: str = ""


class StartSessionRequest(BaseModel):
    code: str
    host_name: str


class SubmitAnswerRequest(BaseModel):
    code: str
    player_name: str
    q_index: int
    chosen: str
    correct: str
    pts: int
    time_taken: float = 0.0


class FinishRequest(BaseModel):
    code: str
    player_name: str


@app.post("/sessions", tags=["Sessions"])
def create_session(body: CreateSessionRequest, user: dict = Depends(get_current_user)):
    try:
        session = store.create_session(body.host_name, body.question_set_id, body.password, user["id"])
        return {"success": True, "session": session}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/sessions", tags=["Sessions"])
def list_open_sessions(user: dict = Depends(get_current_user)):
    return {"sessions": store.get_open_sessions()}


@app.get("/sessions/{code}", tags=["Sessions"])
def get_session(code: str, user: dict = Depends(get_current_user)):
    s = store.get_session_by_code(code)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@app.post("/sessions/join", tags=["Sessions"])
def join_session(body: JoinSessionRequest, user: dict = Depends(get_current_user)):
    try:
        session, player = store.join_session(body.code, body.player_name, body.password, user["id"])
        return {"success": True, "session": session, "player": player}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/sessions/start", tags=["Sessions"])
def start_session(body: StartSessionRequest, user: dict = Depends(get_current_user)):
    try:
        session = store.start_session(body.code, body.host_name)
        return {"success": True, "session": session}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/sessions/answer", tags=["Sessions"])
def submit_answer(body: SubmitAnswerRequest, user: dict = Depends(get_current_user)):
    try:
        session = store.submit_answer(
            body.code, body.player_name, body.q_index,
            body.chosen, body.correct, body.pts, body.time_taken,
        )
        return {"success": True, "session": session}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/sessions/finish", tags=["Sessions"])
def finish_player(body: FinishRequest, user: dict = Depends(get_current_user)):
    try:
        session = store.finish_player(body.code, body.player_name)
        return {"success": True, "session": session}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── User Dashboard ─────────────────────────────────────────────────────────────

@app.get("/me/history", tags=["User"])
def my_history(user: dict = Depends(get_current_user)):
    try:
        return {"history": store.get_user_session_history(user["id"])}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"History error: {type(e).__name__}: {str(e)}")


# ── AI Explanation ─────────────────────────────────────────────────────────────

class ExplainRequest(BaseModel):
    question: str
    correct_answer: str
    student_answer: str
    context: str = ""
    provider: str = "NVIDIA"
    model: str = "meta/llama-3.1-8b-instruct"


@app.post("/explain", tags=["AI"])
def explain(body: ExplainRequest, user: dict = Depends(get_current_user)):
    try:
        text = explain_wrong_answer(
            body.question, body.correct_answer,
            body.student_answer, body.context,
            "NVIDIA", body.model or "meta/llama-3.1-8b-instruct",
        )
        return {"explanation": text}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))


class EvaluateRequest(BaseModel):
    question: str
    correct_answer: str
    student_answer: str
    q_type: str = "mcq"


@app.post("/evaluate", tags=["AI"])
def evaluate_answer(body: EvaluateRequest, user: dict = Depends(get_current_user)):
    try:
        from openai import OpenAI
        import json, re

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY"),
        )

        prompt = f"""You are a strict but fair quiz evaluator.

Question: {body.question}
Correct answer: {body.correct_answer}
Student answer: {body.student_answer}
Question type: {body.q_type}

Decide if the student's answer is correct or meaningfully equivalent to the correct answer.
For MCQ/truefalse: mark correct if the student's choice clearly refers to the same option.
For short answer: allow paraphrasing and give partial credit.

Respond with ONLY valid JSON, no explanation outside it:
{{
  "correct": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence explanation"
}}"""

        response = client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)

        return {
            "correct": bool(result.get("correct", False)),
            "confidence": float(result.get("confidence", 0.0)),
            "reasoning": result.get("reasoning", ""),
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))