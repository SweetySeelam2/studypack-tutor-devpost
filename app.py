# app.py
import os
import json
import re
import time
from typing import List, Dict, Optional, Tuple

from flask import Flask, request, jsonify
import requests
from flask import Response

# --------- Retrieval (offline study packs) ----------
import PyPDF2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------------------- OLLAMA CONFIG --------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")

# Separate connect/read timeouts (seconds)
CONNECT_TIMEOUT = int(os.environ.get("CONNECT_TIMEOUT", "15"))
READ_TIMEOUT = int(os.environ.get("READ_TIMEOUT", "300"))   # allow long generations

# How many retries if Ollama is cold/busy
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
RETRY_BACKOFF = float(os.environ.get("RETRY_BACKOFF", "2.0"))

# -------------------- RAG CONFIG -----------------------
STUDY_PACK_DIR = os.path.join(os.getcwd(), "study_packs")
TOP_K_CHUNKS = 6

# ---- Simple safety guardrails ----
BANNED_PATTERNS = [
    r"\b(?:fuck|shit|bitch|asshole)\b",
    r"\b(?:porn|sexually explicit|erotic)\b",
]
DISALLOWED_TOPICS = [
    "how to make a weapon",
    "self-harm",
    "illegal drugs",
]

def violates_safety(text: str) -> Optional[str]:
    lower = text.lower()
    for pat in BANNED_PATTERNS:
        if re.search(pat, lower):
            return "Inappropriate language"
    for topic in DISALLOWED_TOPICS:
        if topic in lower:
            return f"Disallowed topic: {topic}"
    return None

# -------------- PDF indexing --------------
class StudyPackIndex:
    def __init__(self):
        self.pack_names: List[str] = []
        self.docs_by_pack: Dict[str, List[str]] = {}  # pack -> list of chunks
        self.vectorizers: Dict[str, TfidfVectorizer] = {}
        self.tfidf_mats = {}  # pack -> tf-idf matrix

    @staticmethod
    def _read_text(filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    @staticmethod
    def _read_pdf(filepath: str) -> str:
        text = []
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text.append(page.extract_text() or "")
                except Exception:
                    text.append("")
        return "\n".join(text)

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 1800) -> List[str]:
        chunks, i = [], 0
        while i < len(text):
            j = min(len(text), i + max_chars)
            chunks.append(text[i:j])
            i = j
        return [c.strip() for c in chunks if c.strip()]

    def _index_pack(self, pack_name: str, paths: List[str]):
        all_chunks = []
        for p in paths:
            if p.lower().endswith(".pdf"):
                txt = self._read_pdf(p)
            else:
                txt = self._read_text(p)  # .txt or .md
            chunks = self._chunk_text(txt)
            all_chunks.extend(chunks)

        if not all_chunks:
            return

        vec = TfidfVectorizer(stop_words="english", max_features=30000)
        mat = vec.fit_transform(all_chunks)

        self.pack_names.append(pack_name)
        self.docs_by_pack[pack_name] = all_chunks
        self.vectorizers[pack_name] = vec
        self.tfidf_mats[pack_name] = mat

    def build_from_folder(self, base_dir: str):
        if not os.path.isdir(base_dir):
            return

        subfolders = [d for d in os.listdir(base_dir)
                      if os.path.isdir(os.path.join(base_dir, d))]

        exts = (".pdf", ".txt", ".md")

        # Index subfolders
        for folder in subfolders:
            folder_path = os.path.join(base_dir, folder)
            files = [os.path.join(folder_path, f)
                     for f in os.listdir(folder_path)
                     if f.lower().endswith(exts)]
            if files:
                self._index_pack(folder, files)

        # Root-level files -> "General"
        root_files = [os.path.join(base_dir, f)
                      for f in os.listdir(base_dir)
                      if f.lower().endswith(exts)]
        if root_files:
            self._index_pack("General", root_files)

    def retrieve(self, pack_name: str, query: str, top_k: int = TOP_K_CHUNKS) -> List[Tuple[str, float]]:
        if pack_name not in self.vectorizers:
            return []
        vec = self.vectorizers[pack_name]
        mat = self.tfidf_mats[pack_name]
        qv = vec.transform([query])
        sims = cosine_similarity(qv, mat).ravel()
        if sims.size == 0:
            return []
        idxs = sims.argsort()[::-1][:top_k]
        chunks = self.docs_by_pack[pack_name]
        return [(chunks[i], float(sims[i])) for i in idxs]

index = StudyPackIndex()
index.build_from_folder(STUDY_PACK_DIR)

# -------------- Flask --------------
app = Flask(__name__)

def _ollama_chat_request(payload: Dict) -> Dict:
    """POST to Ollama with retries and clear errors."""
    url = f"{OLLAMA_HOST}/api/chat"
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.post(
                url, json=payload,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
            r.raise_for_status()
            data = r.json()
            # Some Ollama errors come back inside JSON
            if "error" in data and data["error"]:
                return {"_error": f"Ollama error: {data['error']}"}
            return data
        except requests.RequestException as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
            else:
                return {"_error": f"Ollama request failed: {e}"}
    return {"_error": f"Ollama request failed: {last_err}"}

def call_ollama_chat(messages: List[Dict], temperature: float, max_tokens: int) -> str:
    """
    Use Ollama's /api/chat endpoint to interact with the local gpt-oss model.
    We keep generations short by default to reduce timeouts.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.1,
            # You can tune num_ctx if needed:
            # "num_ctx": 4096,
        },
        "stream": False
    }
    data = _ollama_chat_request(payload)
    if "_error" in data:
        raise requests.RequestException(data["_error"])
    return data.get("message", {}).get("content", "")

def call_ollama_chat_stream(messages, temperature=1.0, max_tokens=512):
    """Stream tokens from Ollama as they generate. Yields text chunks."""
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
        "stream": True
    }
    with requests.post(url, json=payload, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunk = obj.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
            except Exception:
                continue

@app.route("/ask_stream", methods=["POST"])
def ask_stream():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    pack = data.get("pack")
    reading_level = data.get("reading_level")
    bilingual_lang = data.get("bilingual_lang")
    max_tokens = int(data.get("max_tokens") or 300)

    reason = violates_safety(question)
    if reason:
        return jsonify({"error": f"Blocked by safety guardrails: {reason}"}), 400

    system_msg = build_system_prompt(reading_level, bilingual_lang)
    context_chunks = [c for c, _ in index.retrieve(pack, question, top_k=TOP_K_CHUNKS)] if pack else []
    content_directive = rag_instructions(context_chunks)

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"{content_directive}\n\nUser question: {question}"},
    ]

    def generate():
        try:
            for chunk in call_ollama_chat_stream(messages, temperature=0.7, max_tokens=max_tokens):
                yield chunk
        except requests.RequestException as e:
            yield f"\n\n[Error] Ollama request failed: {e}"

    return Response(generate(), mimetype="text/plain")

def build_system_prompt(reading_level: Optional[str], bilingual_lang: Optional[str]) -> str:
    base = [
        "You are an offline Educational Tutor.",
        "Be clear, concise, step-by-step.",
        "Use safe, age-appropriate language.",
        "Respond in clean **Markdown** with short sections, headings, and bullet lists.",
        "Use line breaks; avoid giant single paragraphs.",                                 
    ]
    if reading_level:
        base.append(f"Adjust explanations for a Grade {reading_level} reading level.")
    if bilingual_lang and bilingual_lang.lower() != "english":
        base.append(f"Provide bilingual output: first English, then the same content in {bilingual_lang}.")
    return " ".join(base)

def rag_instructions(chunks: List[str]) -> str:
    if not chunks:
        return "Use general knowledge only."
    joined = "\n\n".join([f"[Source {i+1}]\n{c}" for i, c in enumerate(chunks)])
    return (
        "Use ONLY the following study pack excerpts to answer. "
        "If the answer is not contained here, say you don’t have that in the study pack.\n\n"
        f"{joined}\n\n"
        "Cite the source numbers you used (e.g., [Source 1], [Source 3])."
    )

# -------- Health endpoint (useful for debugging) ----------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "packs": index.pack_names, "model": OLLAMA_MODEL})

@app.route("/packs", methods=["GET"])
def list_packs():
    return jsonify({"packs": index.pack_names})

# ----- Tutor chat -----
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    pack = data.get("pack")
    reading_level = data.get("reading_level")
    bilingual_lang = data.get("bilingual_lang")
    # from UI slider; fall back to 300
    max_tokens = int(data.get("max_tokens") or 300)

    reason = violates_safety(question)
    if reason:
        return jsonify({"error": f"Blocked by safety guardrails: {reason}"}), 400

    system_msg = build_system_prompt(reading_level, bilingual_lang)
    context_chunks = []
    if pack:
        context_chunks = [c for c, _ in index.retrieve(pack, question, top_k=TOP_K_CHUNKS)]
    content_directive = rag_instructions(context_chunks)

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"{content_directive}\n\nUser question: {question}"},
    ]

    try:
        answer = call_ollama_chat(messages, temperature=0.7, max_tokens=max_tokens)
        return jsonify({"response": answer})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502

# ----- Lesson generator -----
@app.route("/generate_lesson", methods=["POST"])
def generate_lesson():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    minutes = int(data.get("minutes", 20))
    pack = data.get("pack")
    reading_level = data.get("reading_level")
    bilingual_lang = data.get("bilingual_lang")
    max_tokens = int(data.get("max_tokens") or 600)

    reason = violates_safety(topic)
    if reason:
        return jsonify({"error": f"Blocked by safety guardrails: {reason}"}), 400

    system_msg = build_system_prompt(reading_level, bilingual_lang)
    chunks = []
    if pack:
        chunks = [c for c, _ in index.retrieve(pack, topic, top_k=TOP_K_CHUNKS)]

    directive = rag_instructions(chunks)
    prompt = (
        f"{directive}\n\n"
        f"Create a {minutes}-minute lesson plan on '{topic}'. "
        "Include: Objectives, Hook, Mini-lesson steps, Guided practice, Independent practice, "
        "Differentiation ideas, and an Exit Ticket. Keep it practical for a teacher."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    try:
        answer = call_ollama_chat(messages, temperature=0.8, max_tokens=max_tokens)
        return jsonify({"lesson": answer})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502

# ----- Quiz generator -----
@app.route("/generate_quiz", methods=["POST"])
def generate_quiz():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    count = int(data.get("count", 5))
    pack = data.get("pack")
    reading_level = data.get("reading_level")
    bilingual_lang = data.get("bilingual_lang")
    max_tokens = int(data.get("max_tokens") or 600)

    reason = violates_safety(topic)
    if reason:
        return jsonify({"error": f"Blocked by safety guardrails: {reason}"}), 400

    system_msg = build_system_prompt(reading_level, bilingual_lang)
    chunks = []
    if pack:
        chunks = [c for c, _ in index.retrieve(pack, topic, top_k=TOP_K_CHUNKS)]

    directive = rag_instructions(chunks)
    prompt = (
        f"{directive}\n\n"
        f"Generate a {count}-question quiz on '{topic}'. "
        "Return strict JSON with fields: "
        "questions:[{number:int, question:str, choices:[str] (optional), answer:str}], "
        "and explanations:[str]. Limit explanations to 1-2 sentences each."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = call_ollama_chat(messages, temperature=0.7, max_tokens=max_tokens)
        try:
            data_out = json.loads(raw)
        except Exception:
            data_out = {"questions": [], "explanations": [], "raw": raw}
        return jsonify(data_out)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502

# ----- Auto-grader -----
@app.route("/grade_quiz", methods=["POST"])
def grade_quiz():
    data = request.get_json(force=True)
    quiz_json = data.get("quiz_json")
    student_answers = data.get("student_answers", {})
    pack = data.get("pack")
    reading_level = data.get("reading_level")
    bilingual_lang = data.get("bilingual_lang")
    max_tokens = int(data.get("max_tokens") or 600)

    if not isinstance(quiz_json, dict) or "questions" not in quiz_json:
        return jsonify({"error": "Invalid quiz_json"}), 400

    system_msg = build_system_prompt(reading_level, bilingual_lang)
    chunks = []
    if pack:
        chunks = [c for c, _ in index.retrieve(pack, "grading rubric", top_k=TOP_K_CHUNKS)]

    directive = rag_instructions(chunks)
    prompt = (
        f"{directive}\n\n"
        "You are an auto-grader. Compare 'student_answers' against the quiz 'answer' fields. "
        "Return strict JSON: {"
        "'score': int, 'total': int, "
        "'per_question': [{'number': int, 'student': str, 'correct': bool, 'explanation': str}], "
        "'feedback_summary': str}"
        f"\nQUIZ_JSON:\n{json.dumps(quiz_json, ensure_ascii=False)}\n"
        f"STUDENT_ANSWERS:\n{json.dumps(student_answers, ensure_ascii=False)}"
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = call_ollama_chat(messages, temperature=0.6, max_tokens=max_tokens)
        try:
            graded = json.loads(raw)
        except Exception:
            graded = {"raw": raw}
        return jsonify(graded)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    print(f"Loaded study packs: {index.pack_names}")
    # Turn OFF debug/reloader to prevent stream disconnects on Windows.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)