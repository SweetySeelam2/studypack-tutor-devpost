# StudyPack Tutor — Offline Classroom Copilot

A private, offline tutor that answers **only** from your study packs and generates lessons, quizzes, and auto-grades—no internet required.

---

## Elevator Pitch
A private, offline tutor that answers **only** from your study packs and generates lessons, quizzes, and auto-grades—no internet required.

---

## Category Selection
- **Best Local Agent (primary):** The whole agentic loop (retrieve → plan → answer/quiz/grade) runs locally via Ollama + TF-IDF RAG, with zero network calls.
- **For Humanity (secondary):** Designed for low-connectivity and high-privacy schools; bilingual and grade-level controls expand access.

---

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

## Quick Start - Testing Instructions

**0) Requirements**

Python 3.9–3.12

pip (or uv/pipx)

Ollama (local LLM runtime)

Git (optional, for cloning)

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
  Samples/
    math_multiples_of_5.md         # tiny math facts + 3-item quiz context
    bio_cell_organelles.txt        # short organelles notes
    english_figures_of_speech.md   # simile vs metaphor mini-cheatsheet

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

**6) Quick “Happy-Path” verification** (≤ 3 minutes)**

**Sidebar** → Study Pack (RAG): it should auto-select Samples.

**Tutor Chat tab** → Preset dropdown: choose any preset and click Ask preset.

Expected: a short, well-formatted Markdown answer (bullets, headings).

**Lesson Generator tab:**

Topic: Cell organelles → Generate

Expected: a compact plan with sections (Objectives, Hook, Steps, Practice, Exit Ticket).

**Quiz + Auto-Grader tab:**

Topic: Multiples of 5 (Grade 6); Questions: 3 → Generate

Answer the items (one radio or short text per question) → Grade

Expected: a score out of 3, per-question correctness, brief explanations, and a feedback summary.

If any tab feels slow, slide Max answer tokens down (250–450) and toggle off Bilingual mode in the sidebar.

**7) Health & API smoke tests**

Health
```
curl http://127.0.0.1:5000/health
```
{"status":"ok","packs":["Samples", ...],"model":"gpt-oss:20b"}

**List packs**
```
curl http://127.0.0.1:5000/packs
```
{"packs":["Samples", ...]}

**Ask (non-stream)**
```
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is a metaphor? Give two examples.",
       "pack":"Samples","reading_level":"6",
       "bilingual_lang":"English","max_tokens":300}'
```

**Generate quiz (strict JSON response)**
```
curl -X POST http://127.0.0.1:5000/generate_quiz \
  -H "Content-Type: application/json" \
  -d '{"topic":"Multiples of 5 (Grade 6)","count":3,
       "pack":"Samples","reading_level":"6","bilingual_lang":"English",
       "max_tokens":450}'
```

**Grade quiz**

Use the previous response as quiz_json and craft answers:
```
curl -X POST http://127.0.0.1:5000/grade_quiz \
  -H "Content-Type: application/json" \
  -d '{
    "quiz_json": { ... the JSON you got from /generate_quiz ... },
    "student_answers": {"1":"Yes","2":"No","3":"Yes"},
    "pack":"Samples","reading_level":"6","bilingual_lang":"English","max_tokens":500
  }'
  ```
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

- Github Repo:https://github.com/SweetySeelam2/studypack-tutor-devpost
- Video Demo: https://www.facebook.com/share/p/1CRKCRQwPT/

---

## License

**MIT © 2025 Sweety Seelam**