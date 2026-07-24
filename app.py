import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "hvac_agent.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="HVAC AI Prospecting Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                contact_name TEXT,
                city TEXT,
                state TEXT,
                website TEXT,
                phone TEXT,
                email TEXT,
                google_rating REAL,
                review_count INTEGER,
                services TEXT,
                notes TEXT,
                score INTEGER,
                status TEXT DEFAULT 'New',
                ai_analysis TEXT,
                outreach_email TEXT,
                call_script TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


init_db()


class ProspectRequest(BaseModel):
    company_name: str
    contact_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    google_rating: Optional[float] = None
    review_count: Optional[int] = None
    services: Optional[str] = None
    notes: Optional[str] = None


def deterministic_score(p: ProspectRequest) -> int:
    score = 35
    if p.website:
        score += 10
    if p.phone:
        score += 8
    if p.email:
        score += 8
    if p.contact_name:
        score += 8
    if p.google_rating is not None:
        if p.google_rating >= 4.5:
            score += 12
        elif p.google_rating >= 4.0:
            score += 8
        elif p.google_rating >= 3.5:
            score += 3
    if p.review_count is not None:
        if p.review_count >= 200:
            score += 12
        elif p.review_count >= 50:
            score += 8
        elif p.review_count >= 10:
            score += 4
    if p.notes and len(p.notes.strip()) > 30:
        score += 5
    return max(0, min(score, 100))


def ai_generate(p: ProspectRequest, base_score: int) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the server. Add it in Render Environment settings.",
        )

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    company_data = p.model_dump()

    prompt = f"""
You are an elite HVAC business-development analyst. Analyze the prospect below for an agency selling AI automation to HVAC contractors.

PROSPECT DATA:
{json.dumps(company_data, indent=2)}

RULE-BASED BASE SCORE: {base_score}/100

Return valid JSON only with this exact structure:
{{
  "final_score": 0,
  "qualification": "Priority Lead|Qualified Lead|Nurture|Skip",
  "verified_facts": ["..."],
  "assumptions": ["..."],
  "pain_points": ["..."],
  "recommended_automations": ["..."],
  "analysis": "A concise 120-200 word analysis",
  "subject": "Cold email subject",
  "email": "A personalized cold email under 180 words",
  "call_script": "A natural cold-call script under 220 words"
}}

Requirements:
- Never invent an owner name, revenue, CRM, ad activity, or website feature.
- Clearly label missing information as an assumption.
- Emphasize booked calls, missed-call text-back, after-hours answering, estimate follow-up, maintenance reminders, review generation, and CRM automation only when relevant.
- Keep outreach credible, local, direct, and non-hypey.
- Do not promise guaranteed revenue.
"""

    response = client.responses.create(
        model=model,
        input=prompt,
        text={"format": {"type": "json_object"}},
    )

    try:
        result = json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI returned invalid JSON.") from exc

    result["final_score"] = max(0, min(int(result.get("final_score", base_score)), 100))
    return result


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse((BASE_DIR / "static" / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "hvac-ai-agent",
        "ai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/prospects")
def list_prospects() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM prospects ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/analyze")
def analyze_prospect(payload: ProspectRequest) -> dict:
    if not payload.company_name.strip():
        raise HTTPException(status_code=400, detail="Company name is required.")

    base_score = deterministic_score(payload)
    result = ai_generate(payload, base_score)

    created_at = datetime.now(timezone.utc).isoformat()
    full_analysis = json.dumps(
        {
            "qualification": result.get("qualification"),
            "verified_facts": result.get("verified_facts", []),
            "assumptions": result.get("assumptions", []),
            "pain_points": result.get("pain_points", []),
            "recommended_automations": result.get("recommended_automations", []),
            "analysis": result.get("analysis", ""),
        },
        ensure_ascii=False,
    )

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO prospects (
                company_name, contact_name, city, state, website, phone, email,
                google_rating, review_count, services, notes, score, status,
                ai_analysis, outreach_email, call_script, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.company_name,
                payload.contact_name,
                payload.city,
                payload.state,
                payload.website,
                payload.phone,
                payload.email,
                payload.google_rating,
                payload.review_count,
                payload.services,
                payload.notes,
                result["final_score"],
                result.get("qualification", "New"),
                full_analysis,
                result.get("email", ""),
                result.get("call_script", ""),
                created_at,
            ),
        )
        prospect_id = cursor.lastrowid

    return {
        "id": prospect_id,
        "base_score": base_score,
        **result,
        "created_at": created_at,
    }


@app.delete("/api/prospects/{prospect_id}")
def delete_prospect(prospect_id: int) -> JSONResponse:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM prospects WHERE id = ?", (prospect_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Prospect not found.")
    return JSONResponse({"deleted": True, "id": prospect_id})
