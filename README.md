# StudyPack Tutor — Offline Classroom Copilot

**Tagline:** A private, offline tutor that answers **only** from your study packs and generates lessons, quizzes, and auto-grades—no internet required.

---

## Elevator Pitch
A private, offline tutor that answers **only** from your study packs and generates lessons, quizzes, and auto-grades—no internet required.

## Category Selection
- **Best Local Agent (primary):** The whole agentic loop (retrieve → plan → answer/quiz/grade) runs locally via Ollama + TF-IDF RAG, with zero network calls.
- **For Humanity (secondary):** Designed for low-connectivity and high-privacy schools; bilingual and grade-level controls expand access.

--

## What it does 
StudyPack Tutor indexes teacher-provided `.pdf/.txt/.md` into “Study Packs.” The Tutor Chat answers questions grounded in those packs (or uses general knowledge if none is selected). The Lesson Generator outputs practical plans (objectives, hook, steps, differentiation, exit ticket). The Quiz + Auto-Grader creates short assessments, collects answers, and grades with concise feedback.

---

## How it works 
A Streamlit UI drives a Flask backend. Uploaded materials are chunked and embedded by a lightweight TF-IDF vectorizer; the top-K chunks condition the local LLM (`gpt-oss:20b` via Ollama). Responses are formatted to clean Markdown for classroom-ready output. A simple safety filter removes inappropriate queries.

---

## Why it matters
Many classrooms have poor connectivity and strict privacy needs. StudyPack Tutor runs entirely on a local machine, grounds every answer in the files, and never sends data to the cloud. It gives teachers a reliable, private copilot that works without internet, respects student data, and stays within the curriculum by grounding answers in the teacher’s own materials.

---

## Key Features
- **Offline RAG** over `.pdf`, `.txt`, `.md` in `study_packs/<PackName>/`
- **Tutor Chat** (general or pack-grounded) with clear inline instructions
- **Lesson Generator** (objectives, hook, steps, differentiation, exit ticket)
- **Quiz + Auto-Grader** (MCQ/short-answer, per-question feedback)
- **Bilingual + Reading level** controls (Grades 3–12)
- **Simple UX**: preset prompts, token controls, and visible pack picker

---

## Architecture
- **Frontend:** Streamlit (tabs: Tutor Chat, Lesson Generator, Quiz + Auto-Grader, Help)
- **Backend:** Flask API (`/ask`, `/ask_stream`, `/generate_lesson`, `/generate_quiz`, `/grade_quiz`)
- **Local LLM:** Ollama running `gpt-oss:20b`
- **Retrieval:** TF-IDF + cosine similarity (scikit-learn) over chunked study pack text
- **Parsing:** PyPDF2 for PDFs; native reads for `.txt/.md`

---

## Quick Start

**1) Prereqs**

- Python 3.10+  
- [Ollama](https://ollama.com/) installed and running

**2) Install deps**

```bash

pip install -r requirements.txt
```

**3) Pull the model and start Ollama**

```bash

ollama pull gpt-oss:20b
ollama serve
```

**4) Prepare study packs**

study_packs/
  Mathematics/
    fractions.md
  Biology/
    osmosis.txt
  Astronomy/
    full_moons_2025.txt

**5) Run**

In terminal #1:

```bash

python app.py
```

In terminal #2:

```bash

streamlit run ui.py
```

Visit: http://localhost:8501

*Tip: If added new files, restart app.py to reindex.*

---

## Environment Variables (optional)

- OLLAMA_HOST (default http://127.0.0.1:11434)

- OLLAMA_MODEL (default gpt-oss:20b)

- CONNECT_TIMEOUT (default 15)

- READ_TIMEOUT (default 300)

---

## API Endpoints

- GET /health → {status, packs, model}

- GET /packs → ["Astronomy", "Biology", ...]

- POST /ask / /ask_stream

- POST /generate_lesson

- POST /generate_quiz

- POST /grade_quiz

---

## Troubleshooting

- Windows stream disconnects: run Flask with debug=False, use_reloader=False (already set).

- PDFs extract poorly: prefer .txt or .md for clean RAG.

- Long answers timing out: lower “Max answer tokens” in the sidebar.

---

## Repo
- Public GitHub with README (install/run), `requirements.txt`, MIT license, and a small sample `study_packs/` folder for testing.

---

## Project Links

- Github Repo:
- Video Demo: 

---

## License

**MIT © 2025 Sweety Seelam**