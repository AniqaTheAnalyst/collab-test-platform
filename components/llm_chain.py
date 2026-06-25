"""
components/llm_chain.py
LangChain-powered question generation with support for
OpenAI, Anthropic Claude, and Google Gemini.
"""

import json
import os
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel, Field

try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
except ImportError:
    ChatNVIDIA = None


# ── Output schema ──────────────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    question: str = Field(description="The question text")
    type: str = Field(description="mcq | truefalse | short")
    options: list[str] = Field(description="Answer choices (empty for short)")
    answer: str = Field(description="The correct answer")
    explanation: str = Field(description="Why this is the correct answer")
    topic_tag: str = Field(description="Short topic label for this question")


class QuestionSet(BaseModel):
    title: str
    subject: str
    time_limit: int
    questions: list[QuizQuestion]


# ── Prompt templates ───────────────────────────────────────────────────────────

MCQ_SYSTEM = """You are an expert academic quiz creator. 
Your job is to create high-quality, clear, unambiguous quiz questions.
Always respond with valid JSON only — no markdown, no backticks, no preamble."""

QUESTION_GENERATION_TEMPLATE = """
Generate exactly {num_questions} quiz questions based on the study material below.

STUDY MATERIAL:
\"\"\"
{material}
\"\"\"

CONFIGURATION:
- Question type: {question_type}
  * mcq = 4 options (A/B/C/D), one correct
  * truefalse = options ["True","False"]
  * short = open-ended, no options list (use empty array [])
  * mixed = mix of all three types
- Difficulty: {difficulty}
  * easy = recall and basic comprehension
  * medium = application and analysis
  * hard = evaluation, synthesis, edge cases
- Focus area (if specified): {focus_area}
- Tone/style: {tone}
  * academic = formal textbook style
  * casual = friendly conversational style
  * challenging = tricky with plausible distractors
- Time per question: {time_limit} seconds

CUSTOM INSTRUCTIONS FROM USER:
{custom_prompt}

OUTPUT FORMAT — respond with this exact JSON structure:
{{
  "title": "<descriptive quiz title>",
  "subject": "<subject/topic name>",
  "time_limit": {time_limit},
  "questions": [
    {{
      "question": "<question text>",
      "type": "mcq",
      "options": ["option A", "option B", "option C", "option D"],
      "answer": "option A",
      "explanation": "<why this is correct>",
      "topic_tag": "<short tag like 'Cell Division'>"
    }}
  ]
}}

Rules:
- For MCQ: wrong options (distractors) must be plausible, not obviously wrong
- For short: answer should be 1-5 words that can be auto-matched
- Every question must be self-contained (no "as mentioned above")
- Distribute questions across the material, don't cluster on one section
- Return ONLY the JSON object, nothing else
"""


# ── LLM loader ────────────────────────────────────────────────────────────────

def _get_env_key(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value and not value.startswith("your-") and value not in {"...", "sk-...", "sk-ant-..."}:
            return value
    return ""


def get_llm(provider: str, model: str, temperature: float = 0.4):
    """Load the appropriate LangChain LLM based on provider."""
    provider_name = (provider or "NVIDIA").strip()

    if provider_name == "NVIDIA":
        if ChatNVIDIA is None:
            raise ImportError("langchain-nvidia-ai-endpoints is not installed")
        api_key = _get_env_key("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA API key not configured. Add NVIDIA_API_KEY to .env")
        return ChatNVIDIA(model=model, temperature=temperature, api_key=api_key)

    if provider_name == "OpenAI":
        from langchain_openai import ChatOpenAI
        api_key = _get_env_key("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not configured. Add OPENAI_API_KEY to .env")
        return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)

    elif provider_name == "Anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = _get_env_key("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not configured. Add ANTHROPIC_API_KEY to .env")
        return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)

    elif provider_name == "Google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = _get_env_key("GOOGLE_API_KEY", "GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Google API key not configured. Add GOOGLE_API_KEY or GEMINI_API_KEY to .env")
        return ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=api_key)

    else:
        raise ValueError(f"Unknown provider: {provider_name}")


# ── Main chain ────────────────────────────────────────────────────────────────

def build_question_chain(provider: str, model: str, temperature: float = 0.4):
    """Build a LangChain pipeline: prompt → LLM → JSON parser."""
    llm = get_llm(provider, model, temperature)

    prompt = ChatPromptTemplate.from_messages([
        ("system", MCQ_SYSTEM),
        ("human", QUESTION_GENERATION_TEMPLATE),
    ])

    chain = prompt | llm | JsonOutputParser()
    return chain


def generate_questions(
    material: str,
    num_questions: int = 5,
    question_type: str = "mcq",
    difficulty: str = "medium",
    time_limit: int = 15,
    focus_area: str = "all topics equally",
    tone: str = "academic",
    custom_prompt: str = "",
    provider: str = "NVIDIA",
    model: str = "meta/llama-3.1-8b-instruct",
    temperature: float = 0.4,
) -> dict:
    """
    Generate quiz questions using LangChain + selected LLM provider.
    Returns a dict matching the QuestionSet schema.
    """
    chain = build_question_chain(provider, model, temperature)

    result = chain.invoke({
        "material": material[:6000],  # Limit context window
        "num_questions": num_questions,
        "question_type": question_type,
        "difficulty": difficulty,
        "time_limit": time_limit,
        "focus_area": focus_area or "all topics equally",
        "tone": tone,
        "custom_prompt": custom_prompt or "No additional instructions.",
    })

    # Normalise: ensure time_limit is set
    if isinstance(result, dict):
        result["time_limit"] = time_limit
        for q in result.get("questions", []):
            if "topic_tag" not in q:
                q["topic_tag"] = ""
            if "explanation" not in q:
                q["explanation"] = ""
    return result


# ── Explanation chain ─────────────────────────────────────────────────────────

EXPLAIN_TEMPLATE = """
A student answered a quiz question wrong. Give a clear, friendly explanation.

Question: {question}
Correct answer: {correct_answer}
Student's answer: {student_answer}
Context from material: {context}

Write 2-3 sentences explaining why the correct answer is right and what the student may have misunderstood.
Keep it encouraging and educational.
"""

def explain_wrong_answer(
    question: str,
    correct_answer: str,
    student_answer: str,
    context: str = "",
    provider: str = "NVIDIA",
    model: str = "meta/llama-3.1-8b-instruct",
) -> str:
    """Generate an AI explanation for a wrong answer."""
    llm = get_llm(provider, model, temperature=0.3)
    prompt = PromptTemplate.from_template(EXPLAIN_TEMPLATE)
    chain = prompt | llm
    result = chain.invoke({
        "question": question,
        "correct_answer": correct_answer,
        "student_answer": student_answer or "(no answer given)",
        "context": context[:1000] if context else "No additional context.",
    })
    return result.content if hasattr(result, "content") else str(result)