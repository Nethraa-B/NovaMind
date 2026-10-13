# NovaMind

NovaMind is a lightweight backend for a multimodal, source-grounded adaptive learning platform focused on database management systems (DBMS). It supports uploading lecture materials, grounding answers in the uploaded course content, generating assessments, updating learner mastery, and providing targeted recommendations.

## Purpose

The backend is designed to demonstrate a complete learning loop for technical subjects:

- upload course material
- parse PDFs, PPT/PPTX, and MP4 content
- store source-grounded chunks in SQLite and optionally ChromaDB
- answer questions with citations from the uploaded course material
- generate and score assessments
- update mastery and weak-topic recommendations
- run a lightweight evaluation workflow when desired

## Architecture

The app is organized into a modular backend with clear responsibilities:

- `backend/app/database.py` initializes SQLAlchemy and the SQLite database.
- `backend/app/models.py` defines the persisted course and learner entities.
- `backend/app/ingestion/` extracts and chunks PDF/PPT/video sources.
- `backend/app/rag/` manages retrieval and prompting.
- `backend/app/assessment/` generates and evaluates assessment items.
- `backend/app/learner/` tracks mastery and recommendations.
- `backend/app/evaluation/` provides optional experiment evaluation.

## Directory structure

```text
novamind/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── llm.py
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── processor.py
│   │   │   ├── pdf_processor.py
│   │   │   ├── ppt_processor.py
│   │   │   └── video_processor.py
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── vector_store.py
│   │   │   ├── retriever.py
│   │   │   └── prompts.py
│   │   ├── assessment/
│   │   │   ├── __init__.py
│   │   │   ├── generator.py
│   │   │   └── evaluator.py
│   │   ├── learner/
│   │   │   ├── __init__.py
│   │   │   ├── mastery.py
│   │   │   ├── recommendations.py
│   │   │   └── misconceptions.py
│   │   └── evaluation/
│   │       ├── __init__.py
│   │       └── evaluator.py
│   ├── data/
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.11+
- A virtual environment
- A compatible OpenAI-compatible API endpoint or model provider if you want LLM-generated answers and question generation
- Optional: Whisper for MP4 transcription support

## Windows setup

From PowerShell:

```powershell
cd "c:\Users\NETHRA BHOOVARAGAVAN\Documents\NovaMind"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Virtual environment creation

```bash
python -m venv .venv
source .venv/bin/activate
# or on Windows:
# .\.venv\Scripts\Activate.ps1
```

## Dependency installation

```bash
cd backend
pip install -r requirements.txt
```

## .env configuration

Copy the example file and fill in the required values:

```bash
copy .env.example .env
```

Then edit `.env` with your actual values:

```env
DATABASE_URL=sqlite:///./data/novamind.db
CHROMA_PERSIST_DIR=./chroma
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://your-openai-compatible-endpoint
LLM_MODEL_NAME=your-model-name
```

The configuration file is `backend/.env`. Set `CORS_ORIGINS` to the comma-separated frontend origins allowed to call the API. The example allows both local Vite hostnames. If you do not configure a live LLM endpoint, the API still runs, but grounded answers return `supported: false`; live evaluation returns a provider-unavailable error rather than fabricated results.

## Start the FastAPI server

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- http://localhost:8000/docs
- http://localhost:8000/health

## Start the frontend

In a second terminal, from the workspace root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (by default, http://127.0.0.1:5173). The frontend uses `http://127.0.0.1:8000` by default. To use another API URL, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` before starting Vite.

## API endpoint overview

- `GET /health`
- `POST /api/upload`
- `GET /api/materials`
- `GET /api/materials/{id}`
- `POST /api/ask`
- `POST /api/assessment/generate`
- `POST /api/assessment/submit`
- `GET /api/learner/mastery`
- `GET /api/learner/weak-topics`
- `GET /api/learner/recommendations`
- `POST /api/evaluation/run`
- `GET /api/evaluation/results`

## Supported file types

- PDF (`.pdf`)
- PowerPoint (`.pptx`)
- Video (`.mp4`)

Other file types are rejected with a clear validation error.

## Video transcription requirements

MP4 transcription is optional and is not part of the default installation. The backend imports Whisper only when available and otherwise reports that transcription is unavailable. A successful transcription requires the `openai-whisper` package, its model files, and ffmpeg; this path has not been verified in the current environment and may require heavyweight dependencies.

## Vector retrieval dependencies

ChromaDB is optional. The current Windows/Python 3.13 environment successfully installed ChromaDB 1.5.9 from binary wheels and retrieved a stored semantic vector from a separate process. Install it from the backend environment to enable persistent retrieval:

```bash
pip install "chromadb>=1.5.9"
```

ChromaDB uses its built-in ONNX MiniLM embedding by default. The first indexing operation may download the embedding model. No Torch or sentence-transformers installation is needed for this path. An optional sentence-transformers override is available, but may add large Torch dependencies:

```bash
pip install "sentence-transformers>=3.2.1"
```

Without ChromaDB, NovaMind uses deterministic, lightweight hash vectors in an in-memory fallback. It is process-local, not persistent, and not semantic; restarting the backend loses the fallback index. Persistent ChromaDB retrieval was verified separately; the default project environment does not install ChromaDB.

The persistent collection stores text chunks and metadata:

- source text
- chunk hash
- material ID
- source name
- source type
- topic
- concept
- location reference

The built-in embedding model is `all-MiniLM-L6-v2` via ONNX. A custom sentence-transformers embedder is used if that optional package is installed.

## Topic relationships

Topic and concept labels are assigned by DBMS keyword rules. A prerequisite edge is added only when an uploaded chunk explicitly states a recognized concept is a prerequisite for another recognized concept. Implicit or conflicting relationships are not inferred; the evidence remains in the source chunk and its location.

## How mastery updates work

Mastery is updated using a transparent, deterministic formula based on:

- previous topic mastery
- question difficulty
- quiz outcome
- repeated mistakes
- topic-level performance

This keeps the learner model explainable and easy to reason about for hackathon demos.

## How to run evaluation

Generate assessment questions from uploaded course material and configure an LLM provider first. The endpoint evaluates up to ten stored assessment questions using live grounded model outputs; it does not change learner mastery.

```bash
curl -X POST http://localhost:8000/api/evaluation/run
curl http://localhost:8000/api/evaluation/results
```

The lightweight report includes supported-response rate (not labeled accuracy), citation validity, and lexical reference token F1 against the stored answer key. Token F1 is a transparent overlap diagnostic, not a semantic quality judge. The endpoint returns `409` if no usable assessment cases exist and `503` if the LLM provider is unavailable. Results are held in memory until the backend restarts.

## Tests

Run the repeatable focused backend suite from `backend`:

```powershell
python -m unittest discover -s tests -v
```

## Troubleshooting

- If the server does not start, verify `python-dotenv` is installed and `.env` is valid.
- If uploads fail, ensure the file extension is supported and the file is not empty.
- If retrieval returns nothing, upload course material or check that the extracted content is not empty.
- If LLM calls fail, confirm `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_NAME` are set correctly.
- If ChromaDB fails, check the `CHROMA_PERSIST_DIR` and that the database directory is writable.

## AI-assisted development disclosure

This project was developed with AI-assisted tooling and iterative code generation. The implementation is intentionally lightweight, explainable, and grounded in uploaded course material rather than relying on fabricated outputs.
