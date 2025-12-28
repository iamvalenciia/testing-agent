---
description: How to run the Computer Use Agent (Backend + Frontend)
---

# Running the Computer Use Agent

This workflow starts both the Python backend and Vue.js frontend for the browser automation agent.

## Prerequisites
- Python 3.10+
- Node.js 18+
- Google API Key with Gemini 2.5 Computer Use access

## Step 1: Setup Backend Environment

```bash
cd agent-backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Step 2: Configure Environment Variables

Create a `.env` file in `agent-backend/`:

```
GOOGLE_API_KEY=your_google_api_key_here
HEADLESS=false
```

## Step 3: Start the Backend

// turbo
```bash
cd agent-backend
python main.py
```

Backend will run at `http://localhost:8000`.

## Step 4: Start the Frontend

// turbo
```bash
cd agent-ui
npm run dev
```

Frontend will run at `http://localhost:5173`.

## Step 5: Use the Agent

1. Open `http://localhost:5173` in your browser
2. Type a task in the chat (e.g., "Go to Google and search for cats")
3. Watch the live screenshot update as the agent works
4. Review the action log for all steps taken
