# HVAC AI Prospecting Agent

A deployable FastAPI application that scores HVAC prospects, separates verified facts from assumptions, identifies automation opportunities, generates personalized cold email copy, creates a cold-call script, and stores leads in a lightweight CRM.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env, then export it or use your preferred env loader.
export OPENAI_API_KEY="your-key"
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

## Deploy to GitHub

```bash
git init
git add .
git commit -m "Deploy HVAC AI prospecting agent"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hvac-ai-agent.git
git push -u origin main
```

## Deploy to Render

1. Push this folder to a GitHub repository.
2. In Render, choose **New > Blueprint**.
3. Connect the repository containing `render.yaml`.
4. Enter your `OPENAI_API_KEY` when Render requests it.
5. Deploy.

The health endpoint is `/health`.

## Security

- Never commit `.env` or your API key.
- Keep outbound email sending behind human approval.
- Only enter verified prospect information.
- Confirm applicable privacy, platform, and anti-spam rules before scraping or sending outreach.
