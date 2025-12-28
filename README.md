# Graphi Connect Automated Testing Framework

This project is a resilient, agentic automated testing framework for Graphi Connect. It utilizes LangGraph for state management, Pinecone for vector storage, and assumes an Excel file ("The Hammer") as the source of truth.

## Prerequisites

- Python 3.10+
- Google Gemini API Key
- Pinecone API Key

## Setup

### 1. Clone the repository (if not already local)

### 2. Create a virtual environment
```bash
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up Pinecone

1. Go to [Pinecone.io](https://www.pinecone.io/) and create a free account
2. In the dashboard, click **API Keys** and copy your API key
3. The index will be auto-created when you run the ingestion, or create manually:
   - Click **Indexes** → **Create Index**
   - Name: `hammer-index`
   - Dimensions: `1536`
   - Metric: `cosine`
   - Cloud: `AWS`, Region: `us-east-1`

### 5. Get Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Click **Get API Key** in the sidebar
3. Create or copy your API key

### 6. Environment Variables

Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

Your `.env` should contain:
```env
GOOGLE_API_KEY=your-gemini-api-key
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENV=gcp-starter
PINECONE_INDEX_NAME=hammer-index
HAMMER_FILE_PATH=data/hammer.xlsm
```

## Usage

### Phase 1: Ingest Hammer Data to Pinecone

Run the ingestion engine to parse The Hammer and store vectors in Pinecone:

```bash
python src/main.py
```

This will:
1. Parse all sheets from The Hammer Excel file (`.xlsm`)
2. Generate embeddings using Gemini `gemini-embedding-001` (1536 dimensions)
3. Upsert vectors to Pinecone with full metadata

**Clean Ingestion (recommended for fresh data):**
```python
from src.agents.librarian import LibrarianAgent

agent = LibrarianAgent()
agent.clean_ingest()  # Deletes old vectors, inserts fresh data
```

---

### Phase 2: Chat with The Hammer (RAG Agent)

Run the interactive CLI to ask questions about The Hammer data:

```bash
python chat_cli.py
```

**Commands:**
| Command | Description |
|---------|-------------|
| `<question>` | Ask anything about The Hammer |
| `help` | Show available commands |
| `stats` | Show Pinecone index statistics |
| `exit` | Quit the chat |

**Example session:**
```
🔨 HAMMER CHAT
You: What are group definitions?

🤖 Assistant:
Based on The Hammer data, group definitions are...

📚 Sources:
  • group_definitions (score: 0.92)
  • master_question_list (score: 0.85)
```

---

### Phase 3: Computer Use Agent (Browser Automation)

Run the interactive browser automation agent with a web UI:

**Terminal 1 - Start Backend:**
```bash
cd agent-backend
..\venv\Scripts\activate   # Windows
python main.py
```

**Terminal 2 - Start Frontend:**
```bash
cd agent-ui
npm run dev
```

**Access the UI:**
Open your browser and go to: [http://localhost:5173](http://localhost:5173)

**How to use:**
1. Type a goal in the chat (e.g., "Go to google.com and search for Graphite Connect")
2. The agent will control a browser to complete the task
3. Watch the Live View for real-time screenshots
4. Use **Stop Testing** to halt execution (browser stays open)
5. Use **Save Workflow** to save reusable workflows
6. Use **📥 Download Report** to export a test report with screenshots

**Stop/Restart the services:**
```powershell
# Kill processes on ports
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force  # Backend
Stop-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess -Force  # Frontend
```

---

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

