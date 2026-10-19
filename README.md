# EvidenceAI 🔬

EvidenceAI is an AI assistant for scientific papers. Upload research PDFs, ask questions, get short and clear answers with exact page citations, and check answers for accuracy.

---

## What It Does

Many AI tools give long answers or include incorrect information when answering questions about research papers. **EvidenceAI** helps solve these problems with the following features:

1. **Direct Answers:** Gives clear, concise answers in 1–2 sentences without unnecessary details or long text copied from the paper.
2. **Exact Page Citations:** Links every answer to verified page numbers (`[Page X]`) in the uploaded paper.
3. **Smart Search:** Automatically chooses the best search method, such as finding paper titles and authors in headers, searching for keywords and metrics, or using semantic search to find relevant concepts.
4. **Claim Fact-Checker:** Checks each sentence in an answer for errors, unsupported claims, and incorrect numbers. Each claim is marked as **Supported**, **Contradicted**, or **Unverified**.
5. **Clean and Responsive Interface:** Provides a simple two-tab interface (**Chat** and **Papers**) that works on mobile, tablet, and desktop.

---

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLite / PostgreSQL
- **Search and AI:** Hybrid search (BM25 + FAISS Dense Vectors), SentenceTransformers, Groq / OpenAI / Ollama
- **Frontend:** HTML5, Vanilla CSS, TypeScript

---

## Quick Start

### 1. Install Dependencies

```powershell
# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install backend packages
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Add your API key to `.env`, for example:

```env
GROQ_API_KEY=gsk_...
```

Or use an OpenAI API key:

```env
OPENAI_API_KEY=sk-...
```

### 3. Build the Frontend

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 4. Run the App

```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Running Tests

Run the following command:

```powershell
pytest
```
