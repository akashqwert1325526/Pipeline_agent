# PipelineMedic 🩺
> **AI-Powered CI/CD Failure Diagnosis & Self-Healing Agent**

PipelineMedic is an intelligent developer-first CI/CD reliability agent. It ingests complex, multi-thousand-line build and test logs from platforms like **GitHub Actions**, **Jenkins**, and **GitLab CI**, isolates genuine root causes, strips out cascading noise, and provides concrete, copy-pasteable remediation steps.

---

## 🌟 Key Features

### 🔍 Expert Log Parsing & Incident Grouping
- **Root Cause Isolation**: Identifies the primary fault (e.g., missing dependencies, compiler errors, OOM, network drops) and treats secondary lifecycle failures (`Process completed with exit code 1`, `npm ERR! code 1`) as supporting context rather than separate diagnosis cards.
- **Cascading Failure Collapse**: Groups related tracebacks, npm script failures, and Docker exit codes into one single actionable incident.
- **Platform Agnostic**: Precision pattern detection for GitHub Actions (`##[group]`), Jenkins (`[Pipeline]`), GitLab CI (`section_start:`), and generic runners.

### 🧠 Environment Correlation & Evidence Extraction
- **Runtime Environment Extraction**: Automatically detects active Python, Node.js, npm, Java versions, OS, Docker base images, and CI flags (`CI=true`, `NODE_ENV`).
- **Context-Aware Recommendations**:
  - Distinguishes development dependencies stripped by `NODE_ENV=production` during CI builds (e.g., Vite).
  - Identifies npm `ERESOLVE` peer dependency clashes and outputs `--legacy-peer-deps` resolution.
  - Pinpoints Docker Hub rate limits (`toomanyrequests`) and generates authenticated registry login fixes.
  - Detects memory exhaustion (Node heap, JVM, Docker OOM) and provides exact memory allocation adjustments.
- **Verifiable Log Evidence**: Highlights exact error lines with visual indicators (`→`), surrounding context lines, and relevant stack frames.

### 📊 Evidence-Based Confidence Scoring
- Confidence is computed from verifiable evidence:
  - Error signature pattern match: `70% base`
  - Stack trace availability: `+8%`
  - Exact file & line number isolated: `+4%`
  - Relevant surrounding context lines: `+3%`
  - Environment context detected: `+3%`
  - Historical memory match: `+5%`
  - Generic exit-code only errors: capped at `20%`

### 💾 Semantic Vector Memory & Learning Loop
- Remembers previously diagnosed failures using vector similarity matching.
- Deduplicates identical incidents using error pattern signatures.
- **Learning Loop**: User feedback ("Worked" / "Didn't work") dynamically boosts success scores for proven fixes in future diagnostic queries.

### 🐙 Direct GitHub Actions Integration
- Connect with your GitHub repository using a Personal Access Token (`repo` or `actions:read` scope).
- Automatically fetch recent failed workflows, pull multi-step zipped logs, and diagnose run failures directly inside the dashboard.

---

## 🏗️ Architecture

```
PipelineMedic/
├── backend/                   # FastAPI Backend
│   ├── app/
│   │   ├── api/               # REST Endpoints (analyze, github, dashboard, feedback, etc.)
│   │   ├── models/            # SQLAlchemy & Pydantic Schemas
│   │   ├── services/
│   │   │   ├── ai_agent.py        # Core expert diagnosis engine & remediation logic
│   │   │   ├── log_parser.py      # Multi-line clustering & environment extractor
│   │   │   ├── vector_memory.py   # Semantic similarity search & learning store
│   │   │   └── github_service.py  # GitHub Actions REST API client
│   │   ├── config.py          # Environment settings
│   │   └── database.py        # SQLite persistence layer
│   ├── tests/                 # 40 Automated regression, parser & API tests
│   └── requirements.txt
│
├── frontend/                  # React 18 + Vite + Tailwind CSS Dashboard
│   ├── src/
│   │   ├── components/        # DiagnosisCard, Layout, metric widgets
│   │   ├── pages/             # Dashboard, AnalyzeLogs, GitHubIntegration, History, Analytics
│   │   └── lib/               # API client and formatting utilities
│   └── package.json
│
├── sample_logs/               # Real-world failure logs for testing
├── docker-compose.yml         # Containerized full-stack deployment
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm
- *(Optional)* Docker & Docker Compose

---

### Option 1: Quickstart on Windows (Scripts)

Double click or run:
```cmd
start.bat
```
This automatically starts both the FastAPI backend on port `8000` and Vite frontend on port `5173`.

---

### Option 2: Manual Setup

#### 1. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
API docs available at: **http://127.0.0.1:8000/docs**

#### 2. Frontend Setup
```bash
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev -- --host 127.0.0.1 --port 5173
```
Dashboard available at: **http://127.0.0.1:5173**

---

### Option 3: Docker Compose
```bash
docker-compose up --build
```

---

## 🧪 Running Automated Tests

PipelineMedic includes an automated test suite covering regression scenarios, error grouping, environment correlation, and API contracts.

### Backend Tests (40 Tests)
```bash
cd backend
python -m pytest tests/ -v
```
Test Suites:
- `tests/test_regression.py`: Verifies Vite grouping, Docker OOM merging, independent failure preservation, and ChromaDB filtering.
- `tests/test_expert_diagnosis.py`: Tests environment extraction, Docker rate limits, npm ERESOLVE peer conflicts, and warning suppression.
- `tests/test_parser.py`: Verifies platform detection, ANSI stripping, and error parsing.
- `tests/test_api.py`: Tests REST endpoints, upload handling, and analytics.

### Frontend Tests
```bash
cd frontend
npx vitest run
```

---

## ⚙️ Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock` for ultra-fast local deterministic engine (<50ms), or `google` / `openai` for LLM enhancement. |
| `GOOGLE_API_KEY` | `""` | Gemini API key for external LLM generation. |
| `OPENAI_API_KEY` | `""` | OpenAI API key (`gpt-4o-mini`). |
| `DATABASE_URL` | `sqlite:///./pipelinemedic.db` | Local SQLite database path. |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Persistent vector memory store directory. |
| `MAX_LOG_SIZE_MB` | `10` | Maximum log upload file size. |

---

## 🛡️ License
MIT License. Built for CI/CD developers and DevOps teams.
