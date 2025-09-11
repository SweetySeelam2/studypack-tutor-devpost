# ui.py
import streamlit as st
import requests
import json
from textwrap import dedent
import re

API_BASE = "http://127.0.0.1:5000"

st.set_page_config(page_title="AI-Powered Educational Assistant", layout="wide")
st.title("AI-Powered Educational Assistant (Offline-Ready)")

# ---------------- Sidebar: global controls ----------------
st.sidebar.header("Controls")

# Fetch packs
try:
    packs = requests.get(f"{API_BASE}/packs", timeout=10).json().get("packs", [])
except Exception:
    packs = []

# Default to "Samples" if that pack exists (index +1 because "(None)" is first)
default_idx = 0
if "Samples" in packs:
    default_idx = packs.index("Samples") + 1

pack_choice = st.sidebar.selectbox(
    "Study Pack (RAG)",
    ["(None)"] + packs,
    index=default_idx
)
pack_send = None if pack_choice == "(None)" else pack_choice

reading_level = st.sidebar.selectbox("Reading level (grades)", ["", "3","4","5","6","7","8","9","10","11","12"])

stream_on = st.sidebar.toggle(
    "Stream responses (show tokens as they arrive)",
    value=True,
    help="On = text appears immediately while the model is still thinking."
)

# --- Bilingual controls (toggle + picker) ---
bi_on = st.sidebar.toggle("Bilingual mode", value=False,
                          help="Off while testing for speed; turn on for final outputs.")
bi_lang = st.sidebar.selectbox(
    "Second language (for bilingual output)",
    ["Spanish", "French", "Hindi", "Arabic", "Chinese", "English"],
    index=0,
    disabled=not bi_on,
    help="When Bilingual mode is ON, the tutor outputs English + this language."
)
# What the backend expects:
bilingual_lang_to_send = bi_lang if bi_on else "English"

st.sidebar.markdown("### Performance")
resp_tokens = st.sidebar.slider("Max answer tokens", min_value=100, max_value=1200, value=300, step=50)

st.sidebar.markdown("---")
st.sidebar.markdown("**Tips**")
st.sidebar.markdown("- Put PDFs/**.txt/.md** in `study_packs/` (subfolders become pack names).")
st.sidebar.markdown("- Use reading level for age-appropriate output.")
st.sidebar.markdown("- Turn off bilingual for speed; turn on for final drafts.")

def _pretty_md(text: str) -> str:
    if not isinstance(text, str):
        return str(text)

    t = text.strip()

    # Normalize bullets the model often emits (•, – , —, hyphens crammed after text)
    t = t.replace("•", "- ").replace("–", "- ").replace("—", "- ")

    # Ensure a blank line before list items and headings
    t = re.sub(r"(?<!\n)\n(-\s+)", r"\n\n\1", t)
    t = re.sub(r"(#+\s*[^\n]+)", r"\n\n\1", t)

    # Promote common inline headers to real H3
    headers = [
        "Definition", "Examples", "Steps", "Answer", "Tips",
        "Objectives", "Hook", "Mini-lesson", "Guided practice",
        "Independent practice", "Exit Ticket", "Explanation"
    ]
    for h in headers:
        # e.g. "Examples -" or "Examples:" -> "### Examples"
        t = re.sub(rf"\b{h}\s*[-:]\s*", f"\n\n### {h}\n\n", t, flags=re.I)

    # When a sentence is smashed into bullets, force each "- " onto its own line
    t = re.sub(r"\s+-\s+", r"\n- ", t)

    # Put a blank line between paragraphs (two+ sentences jammed together)
    t = re.sub(r"([.!?])\s+(?=[A-Z(])", r"\1  ", t)   # keep two spaces after sentence end
    t = re.sub(r"\n{3,}", "\n\n", t)                  # collapse extra blank lines

    return t.strip()

# ---------------- Tabs ----------------
tabs = st.tabs(["Tutor Chat", "Lesson Generator", "Quiz + Auto-Grader", "Help"])

# ----------------- Tutor Chat -----------------
with tabs[0]:
    st.subheader("Ask the Tutor")

    # Inline instructions
    st.info(
        "How to use • Tutor Chat\n"
        "1) (Optional) Pick a **Study Pack (RAG)** in the sidebar to restrict answers to your files.\n"
        "2) Choose **Reading level** and (optional) **Bilingual mode**.\n"
        "3) Adjust **Max answer tokens** (200–300 for Q&A is fast and reliable).\n"
        "4) Ask a question or use a preset."
    )

    # --- Prompt presets by pack (General used if none selected) ---
    PRESETS = {
        "Samples": [
            "Grade 6: Are these numbers multiples of 5: 30, 47, 145? Explain why.",
            "Create a 3-question quiz on cell organelles (Grade 6) with answers.",
            "Explain simile vs. metaphor with two examples each."
        ],
        
        "General": [
            "Explain photosynthesis in 3 short steps.",
            "What are even and odd numbers? Give two examples of each.",
            "Summarize the causes of the water cycle in 4 bullet points."
        ],
        "Mathematics": [
            "Explain equivalent fractions with one worked example.",
            "How do you find the LCM of 8 and 12? Show steps.",
            "Create 5 practice problems on multiplying fractions (with answers)."
        ],
        "Biology": [
            "Define osmosis and diffusion; contrast them in a table.",
            "Explain the function of mitochondria at a Grade 6 level.",
            "Make a 5-question quiz on cell organelles (with answers)."
        ],
        "Astronomy": [
            "What is a full moon and how often does it occur?",
            "Why do we have seasons? Explain simply.",
            "Describe the phases of the moon in order."
        ],
        "English": [
            "What is a simile vs. a metaphor? Give 2 examples of each.",
            "Rewrite this sentence at Grade 5 level: 'Photosynthesis converts solar energy into chemical energy.'",
            "Create a short reading passage (120 words) and 3 comprehension questions."
        ],
        "History": [
            "Explain causes and effects of the Industrial Revolution in 5 bullets.",
            "Who was Mahatma Gandhi? Summarize in 5 sentences.",
            "Make a compare/contrast chart for Athens vs. Sparta (3 rows)."
        ],
        "ComputerScience": [
            "Explain what an algorithm is, with a cooking analogy.",
            "What is a variable and a loop? Give tiny Python examples.",
            "Make 3 beginner Python exercises with answers."
        ],
    }

    # ---------- 1) Ask box + Ask button (TOP) ----------
    row1_q, row1_btn = st.columns([10, 1.2])
    with row1_q:
        q = st.text_input("Your question", label_visibility="collapsed",
                          placeholder="Ask something…", key="q_input")
    with row1_btn:
        ask_clicked = st.button("Ask", type="primary", use_container_width=True, key="ask_btn")

    st.divider()

    # ---------- 2) Preset dropdown (BELOW), then Ask preset button ----------
    st.caption("Or pick a prompt preset")
    preset_group = pack_send if pack_send in PRESETS else "General"
    preset = st.selectbox("Prompt preset", PRESETS[preset_group],
                          key="preset_select", label_visibility="collapsed")
    ask_preset_clicked = st.button("Ask preset", key="ask_preset_btn")

    # ---------- Helper to send either free-text or preset ----------
    def send_question(text: str):
        payload = {
            "question": text.strip(),
            "pack": pack_send,
            "reading_level": reading_level or None,
            "bilingual_lang": bilingual_lang_to_send,
            "max_tokens": int(resp_tokens),
        }
        placeholder = st.empty()
        if stream_on:
            try:
                with st.spinner("Thinking (streaming)…"):
                    res = requests.post(f"{API_BASE}/ask_stream", json=payload, stream=True, timeout=300)
                    res.raise_for_status()
                    buf = ""
                    for line in res.iter_lines(decode_unicode=True):
                        if line:
                            buf += line
                            placeholder.markdown(buf)      # live while streaming
                    placeholder.markdown(_pretty_md(buf))  # pretty final render
            except Exception as e:
                st.error(f"Streaming failed: {e}")
        else:
            with st.spinner("Thinking…"):
                try:
                    r = requests.post(f"{API_BASE}/ask", json=payload, timeout=180)
                    data = r.json()
                    if r.status_code == 200:
                        placeholder.markdown(_pretty_md(data.get("response", "(no content)")))
                    else:
                        st.error(data.get("error", f"HTTP {r.status_code}"))
                except Exception as e:
                    st.error(f"Request failed: {e}")

    # Click handlers
    if ask_clicked:
        if not q.strip():
            st.warning("Enter a question.")
        else:
            send_question(q)
    if ask_preset_clicked:
        send_question(preset)

# --------------- Lesson Generator --------------
with tabs[1]:
    st.subheader("One-Click Lesson Plan")
    st.info(
        "How to use • Lesson Generator\n"
        "1) Type a **Topic** and choose **Minutes**.\n"
        "2) (Optional) Select a **Study Pack** to constrain content to your files.\n"
        "3) **Max answer tokens** ~ 450–600 gives fuller plans; lower it for speed.\n"
        "4) Click **Generate**."
    )

    colA, colB, colC = st.columns([5,2,1])
    with colA:
        topic = st.text_input("Topic (e.g., Photosynthesis)", placeholder="e.g., Osmosis")
    with colB:
        minutes = st.number_input("Minutes", min_value=5, max_value=120, value=20, step=5)
    with colC:
        gen_lesson = st.button("Generate", type="primary", key="gen_lesson_btn")

    if gen_lesson:
        if not topic.strip():
            st.warning("Enter a topic.")
        else:
            payload = {
                "topic": topic.strip(),
                "minutes": minutes,
                "pack": pack_send,
                "reading_level": reading_level or None,
                "bilingual_lang": bilingual_lang_to_send,
                "max_tokens": max(resp_tokens, 400)  # lesson needs a bit more room
            }
            with st.spinner("Generating lesson…"):
                try:
                    r = requests.post(f"{API_BASE}/generate_lesson", json=payload, timeout=360)
                    data = r.json()
                    if r.status_code == 200:
                        st.success("Lesson Plan")
                        st.markdown(_pretty_md(data.get("lesson","(no content)")))
                    else:
                        st.error(data.get("error", f"HTTP {r.status_code}"))
                except Exception as e:
                    st.error(f"Request failed: {e}")

# --------------- Quiz + Auto-Grader --------------
with tabs[2]:
    st.subheader("Create Quiz")
    st.info(
        "How to use • Quiz + Auto-Grader\n"
        "1) Enter **Quiz topic** and number of **Questions**.\n"
        "2) (Optional) Pick a **Study Pack** for source-anchored questions.\n"
        "3) Click **Generate** → answer the questions → click **Grade**.\n"
        "4) If it feels slow, lower **Max answer tokens** to ~450."
    )
    
    c1, c2, c3 = st.columns([5,1,1])
    with c1:
        quiz_topic = st.text_input("Quiz topic (e.g., Grade 6 Fractions)", placeholder="e.g., Multiples of 5")
    with c2:
        q_count = st.number_input("Questions", 3, 20, 5)
    with c3:
        gen_quiz = st.button("Generate", type="primary", key="gen_quiz_btn")

    if "last_quiz" not in st.session_state:
        st.session_state["last_quiz"] = None

    if gen_quiz:
        if not quiz_topic.strip():
            st.warning("Enter a quiz topic.")
        else:
            payload = {
                "topic": quiz_topic.strip(),
                "count": int(q_count),
                "pack": pack_send,
                "reading_level": reading_level or None,
                "bilingual_lang": bilingual_lang_to_send,
                "max_tokens": max(resp_tokens, 450)
            }
            with st.spinner("Creating quiz…"):
                try:
                    r = requests.post(f"{API_BASE}/generate_quiz", json=payload, timeout=360)
                    quiz = r.json()
                    if r.status_code == 200:
                        st.session_state["last_quiz"] = quiz
                        st.success("Quiz generated below")
                    else:
                        st.error(quiz.get("error", f"HTTP {r.status_code}"))
                except Exception as e:
                    st.error(f"Request failed: {e}")

    quiz = st.session_state.get("last_quiz")
    if quiz:
        st.markdown("### Quiz")
        answers = {}
        for item in quiz.get("questions", []):
            num = item.get("number")
            prompt = item.get("question", f"Question {num}")
            choices = item.get("choices")

            if choices and isinstance(choices, list) and choices:
                ans = st.radio(f"{num}. {prompt}", choices, key=f"q{num}")
            else:
                ans = st.text_input(f"{num}. {prompt}", key=f"q{num}")
            answers[str(num)] = ans

        grade_clicked = st.button("Grade", type="primary", key="grade_btn")
        if grade_clicked:
            payload = {
                "quiz_json": quiz,
                "student_answers": answers,
                "pack": pack_send,
                "reading_level": reading_level or None,
                "bilingual_lang": bilingual_lang_to_send,
                "max_tokens": max(resp_tokens, 500)
            }
            with st.spinner("Grading…"):
                try:
                    r = requests.post(f"{API_BASE}/grade_quiz", json=payload, timeout=360)
                    graded = r.json()
                    if r.status_code == 200:
                        st.success(f"Score: {graded.get('score','?')}/{graded.get('total','?')}")
                        details = graded.get("per_question") or []
                        for row in details:
                            ok = "✅" if row.get("correct") else "❌"
                            st.markdown(f"**Q{row.get('number')}** {ok} — Your answer: _{row.get('student','')}_")
                            st.write(_pretty_md(row.get("explanation","")))
                        st.markdown("---")
                        st.markdown("**Feedback Summary**")
                        st.write(_pretty_md(graded.get("feedback_summary","")))
                        if "raw" in graded:
                            with st.expander("Raw model output"):
                                st.code(graded["raw"])
                    else:
                        st.error(graded.get("error", f"HTTP {r.status_code}"))
                except Exception as e:
                    st.error(f"Request failed: {e}")

# ----------------- Help Tab -----------------
with tabs[3]:
    st.subheader("How to use this app")
    st.markdown(dedent("""
    **Launch order every time**
    1. Terminal #1: `python app.py`
    2. Terminal #2: `streamlit run ui.py`
    If you add PDFs, restart **app.py**.

    **Study Pack (RAG)**
    - Put files in `study_packs/YourPack/` (**.pdf, .txt, .md**). Each subfolder becomes a pack.
    - Select the pack before asking/generating to force answers from that content.
    - If not found in the pack, the tutor says it doesn’t appear in the materials.

    **Reading Level & Bilingual**
    - Choose Grades 3–12 for tone & vocabulary.
    - Turn on bilingual to get English + your selected language.

    **Tabs**
    - *Tutor Chat*: Ask quick questions. Works best with a selected pack for accuracy.
    - *Lesson Generator*: One-click lesson plan (objectives, activities, exit ticket).
    - *Quiz + Auto-Grader*: Generate a quiz, collect answers, and auto-grade with a rubric.

    **Performance tips**
    - Use the sidebar **Max answer tokens**: smaller = faster.
    - Turn off bilingual for speed; turn on for your final copy.
    - First request after starting Ollama can be slower (model warm-up).

    **Troubleshooting**
    - If you see an Ollama timeout, try a shorter request, reduce tokens, or ask again (the app auto-retries).
    - Check `http://127.0.0.1:5000/health` to confirm the backend is alive.
    """))