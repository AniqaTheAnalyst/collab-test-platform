# 📚 StudySquad

**StudySquad** is an AI-powered multiplayer study quiz platform. Upload your notes, let an LLM turn them into a quiz, then host a live session and compete with up to 4 friends in real time.

> Built with **Streamlit** (frontend) · **FastAPI** (backend) · **Supabase** (auth + database) · **NVIDIA NIM / LangChain** (question generation & grading)

---

## ✨ Features

- **🔐 Authentication** — Email/password sign-up and sign-in via Supabase Auth.
- **📄 Upload Material** — Add study content by pasting text, uploading a PDF, or uploading an image (handwritten notes, whiteboard photos, slides). Materials are private to your account.
- **🤖 AI Question Generation** — Fully configurable quiz generation:
  - Question types: Multiple Choice, True/False, Short Answer, or Mixed
  - Difficulty: Easy / Medium / Hard
  - Tone: Academic, Casual, or Challenging
  - Custom focus areas and free-form prompt engineering instructions
  - Adjustable question count, time limit per question, and AI creativity (temperature)
- **👑 Host Live Sessions** — Create a session, get a shareable join code, and host up to 5 players (including yourself) in a synchronized quiz.
- **🏃 Join Sessions** — Join with a code (and optional password), answer questions against a live countdown timer.
- **🧠 AI Grading** — Short-answer and free-text responses are graded by an LLM for semantic correctness rather than exact string matching, with confidence-weighted scoring.
- **⚡ Speed-Based Scoring** — Points reward both correctness and speed.
- **📊 Results & Review** — Post-quiz leaderboard, per-question breakdown, and on-demand AI explanations for missed questions.
- **📁 Personal Dashboard** — Quiz history, saved materials, and generated question sets, all scoped to your account.

---

## 🖼️ Screens

| Home | Upload Material | Generate Questions |
|---|---|---|
| Welcome dashboard with quick actions and stats | Paste text / upload PDF / upload image | Configure type, difficulty, tone, and custom prompts |

| Host Session | Join Session | My Dashboard |
|---|---|---|
| Create a session and share the join code | Enter a code to join a live quiz | Review history, materials, and question sets |

---

## 🏗️ Architecture

```
┌────────────────────┐        REST (JSON)        ┌──────────────────────┐
│  Streamlit Frontend │ ─────────────────────────▶│   FastAPI Backend     │
│  (pages/*.py)       │◀───────────────────────── │   (api/server.py)     │
└─────────┬───────────┘                           └───────────┬───────────┘
          │                                                    │
          │ Supabase Auth (sign up/in, session)                │ Supabase service client
          ▼                                                    ▼
┌────────────────────┐                            ┌──────────────────────┐
│    Supabase Auth    │                            │   Supabase Postgres   │
└────────────────────┘                            │ materials, question_  │
                                                    │ sets, sessions,       │
                                                    │ session_players,      │
                                                    │ answers               │
                                                    └──────────────────────┘

                 ┌────────────────────────────┐
                 │   LangChain + NVIDIA NIM    │
                 │  (question generation,      │
                 │   explanations, grading)    │
                 └────────────────────────────┘
```

- The Streamlit app authenticates users against **Supabase Auth**, then calls the FastAPI backend for all data operations (materials, question sets, sessions, scoring).
- The backend talks to **Supabase Postgres** using a service-role client, with all queries scoped by `user_id`.
- Question generation, wrong-answer explanations, and short-answer grading are powered by **NVIDIA-hosted LLMs** (`meta/llama-3.1-8b-instruct` by default), orchestrated through **LangChain**. The backend also supports OpenAI, Anthropic, and Google Gemini as alternate providers.

---

## 📂 Project Structure

```
.
├── api/
│   └── server.py              # FastAPI REST API (materials, questions, sessions, AI endpoints)
├── components/
│   ├── auth.py                 # Supabase Auth wrapper (sign up/in/out, session restore)
│   ├── llm_chain.py             # LangChain question-generation & explanation chains
│   ├── quiz_engine.py            # AI-assisted answer evaluation + scoring logic
│   ├── session_store.py          # (legacy) in-memory JSON-file session store
│   └── supabase_store.py          # Supabase-backed persistent data store
├── pages/
│   ├── 0_Auth.py
│   ├── 1_Upload_Material.py
│   ├── 2_Generate_Questions.py
│   ├── 3_Host_Session.py
│   ├── 4_Join_Session.py
│   ├── 5_Results.py
│   └── 6_My_Dashboard.py
├── utils/
│   └── helpers.py                # Shared API client, session state, UI helpers
├── app.py                        # Streamlit entry point / home page
└── .env                          # Environment configuration (not committed)
```

---

## ⚙️ Setup

### 1. Prerequisites

- Python 3.10+
- A [Supabase](https://supabase.com) project (Postgres + Auth)
- An [NVIDIA NIM](https://build.nvidia.com) API key (or OpenAI/Anthropic/Google key, if using another provider)

### 2. Clone & install

```bash
git clone https://github.com/<your-username>/studysquad.git
cd studysquad
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# AI provider (default: NVIDIA)
NVIDIA_API_KEY=your-nvidia-api-key

# Optional alternate providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# Backend URL used by the Streamlit frontend
API_URL=http://localhost:8000
```

### 4. Set up the database

Create the following tables in your Supabase project: `materials`, `question_sets`, `sessions`, `session_players`, `answers`. Each is scoped by `user_id` and referenced by the backend in `components/supabase_store.py`. Row-level security is recommended, since API-level authorization is enforced by the FastAPI layer.

### 5. Run the backend

```bash
uvicorn api.server:app --reload --port 8000
```

### 6. Run the frontend

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`, connecting to the API at the `API_URL` you configured.

---

## 🔌 API Overview

All endpoints (except `/` and `/health`) require authentication via an `X-User-Id` header or a `Bearer` token.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/materials` | Save a new study material |
| `GET` | `/materials` | List the current user's materials |
| `GET` | `/materials/{id}` | Get a single material |
| `POST` | `/generate` | Generate a question set from material via AI |
| `GET` | `/question_sets` | List the current user's question sets |
| `GET` | `/question_sets/{id}` | Get a question set |
| `POST` | `/question_sets/{id}/publish` | Make a question set public |
| `POST` | `/sessions` | Create a new quiz session |
| `GET` | `/sessions` | List open (waiting) sessions |
| `GET` | `/sessions/{code}` | Get session state by join code |
| `POST` | `/sessions/join` | Join a session |
| `POST` | `/sessions/start` | Start a session (host only) |
| `POST` | `/sessions/answer` | Submit an answer |
| `POST` | `/sessions/finish` | Mark a player as finished |
| `GET` | `/me/history` | Get the current user's quiz history |
| `POST` | `/explain` | Get an AI explanation for a wrong answer |
| `POST` | `/evaluate` | AI-graded correctness check for free-text answers |

---

## 🧮 Scoring

Each correct answer earns points based on a base score plus a speed bonus, weighted by the AI's confidence in the answer's correctness:

```
points = (100 + speed_bonus) × confidence
speed_bonus = max(0, (1 − time_taken / time_limit) × 50)
```

Exact-match answers skip the AI grading call entirely and are scored with full confidence.

---

## 🗺️ Roadmap Ideas

- Row-level security policies for all Supabase tables
- WebSocket-based live updates instead of polling
- Support for image-based (OCR) material ingestion end-to-end
- Public quiz library / discovery page
- Additional LLM providers surfaced in the UI (currently NVIDIA-only in the frontend)

---

## 📄 License

Add your preferred license here (e.g. MIT).
