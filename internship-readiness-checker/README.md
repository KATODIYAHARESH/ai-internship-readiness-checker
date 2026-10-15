# 🎯 AI Internship Readiness Checker

A hackathon-ready prototype that tells university students **how ready they are for an internship in a specific role**, *why*, and *exactly what to do next*, while giving the placement cell campus-wide analytics.

**Stack:** Python 3.10+, Streamlit, Pandas, SQLite (required) · Ollama `llama3.2` (optional) · scikit-learn TF-IDF, with optional ChromaDB, for semantic matching.
Runs fully offline on a laptop. The only optional download is the Ollama model.

---

## ✨ Features

| Requirement | Where it lives |
|---|---|
| Explainable readiness score 0-100 (Skills 35, Projects 20, Academics 15, Soft skills 15, Experience 10, Certs 5) and levels Ready ≥75 / Almost 50-74 / Needs work <50 | `readiness/scoring.py` |
| 4 target roles with required + preferred skills, role-specific score | `readiness/data/catalog.json`, `readiness/catalog.py` |
| Skill-gap analysis and personalised action plan (specific learning steps per missing skill, timeline, impact points) | `readiness/recommendations.py` |
| Resume analyzer: paste text or upload PDF, skill extraction, scoring, semantic match to job descriptions | `readiness/resume.py`, `readiness/semantic.py`, `ui/resume_tab.py` |
| Student view: gauge, breakdown chart, gaps, action plan, what-if simulator, Markdown and PDF report | `ui/assessment_view.py`, `readiness/reports.py` |
| Placement dashboard: average score, % ready, by department, top campus skill gaps, at-risk list, CSV export | `readiness/analytics.py`, `ui/dashboard_tab.py` |
| AI mentor with Ollama (llama3.2), grounded in score and gaps, **rule-based fallback** | `readiness/llm.py`, `ui/chat_tab.py` |
| 80 synthetic students seed script | `seed_db.py`, `readiness/seed.py` |
| Caching with `st.cache_data`, no crashes on empty input, type hints and docstrings | `readiness/cache.py`, everywhere |
| Unit tests for the scoring function | `tests/test_scoring.py` |

---

## 🏗️ Architecture (text diagram)

```
┌───────────────────────────── Streamlit UI  (app.py + readiness/ui/*) ─────────────────────────────┐
│  🎓 Student tab   📄 Resume Analyzer   🏫 Placement Dashboard   🤖 AI Mentor   ℹ️ How it works      │
└───────┬───────────────────┬─────────────────────┬─────────────────────────┬───────────────────────┘
        │                   │                     │                         │
        ▼                   ▼                     ▼                         ▼
  service.assess()     resume.py             cache.py (st.cache_data)     llm.ask_mentor()
   │   │   │            PDF/text → skills     │       │                     │          │
   │   │   └─► recommendations.py             ▼       ▼                     ▼          ▼
   │   │        gaps · action plan ·     analytics.py  semantic.py     Ollama API   rule_based_reply()
   │   │        timeline · insights      KPIs · dept   TF-IDF │ Chroma  (llama3.2)  (offline fallback)
   │   └─► scoring.py  ◄─ pure,          gaps · risk   (+Ollama embeddings)
   │        explainable 0-100 score          │
   │                                         ▼
   └─► reports.py (Markdown/PDF)        database.py ──► SQLite  data/readiness.db
                                             ▲
              seed_db.py / seed.py ──────────┘      catalog.json = roles · skills · playbooks · job descriptions
```

**Layers:** data (`database`, `seed`, `catalog`) → scoring (`scoring`) → recommendations (`recommendations`, `service`) → llm (`llm`, `semantic`) → ui (`readiness/ui/*`, `app.py`). Only `cache.py` and `ui/` import Streamlit, so every other module is plain, testable Python.

### File tree

```
internship-readiness-checker/
├── app.py                      # Streamlit entry point
├── seed_db.py                  # CLI: generate 80 synthetic students into SQLite
├── requirements.txt
├── pytest.ini
├── .env.example  .gitignore  .streamlit/config.toml
├── data/                       # readiness.db is created here
├── readiness/
│   ├── config.py               # constants + env vars (no secrets)
│   ├── models.py               # typed dataclasses
│   ├── catalog.py + data/catalog.json
│   ├── database.py             # SQLite schema + loaders
│   ├── seed.py                 # synthetic data generator
│   ├── scoring.py              # explainable score
│   ├── recommendations.py      # gaps, action plan, insights
│   ├── resume.py               # PDF/text → skills
│   ├── semantic.py             # TF-IDF / ChromaDB matching
│   ├── llm.py                  # Ollama + rule-based mentor
│   ├── analytics.py            # campus aggregations
│   ├── reports.py              # Markdown + PDF
│   ├── service.py              # assess() orchestration
│   ├── cache.py                # st.cache_data wrappers
│   └── ui/                     # components, charts, one module per tab
└── tests/
    ├── test_scoring.py         # scoring unit tests
    └── test_pipeline.py        # seed, resume, reports, mentor fallback, analytics
```

---

## 🚀 Setup

```bash
cd internship-readiness-checker
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python seed_db.py            # creates data/readiness.db with 80 students (optional: the app auto-seeds on first run)
streamlit run app.py         # opens http://localhost:8501
pytest                       # run the unit tests
```

`python seed_db.py --count 120 --seed 7` creates a bigger or different cohort. The sidebar's **Dataset tools** does the same from the UI.

### Optional: local LLM mentor (Ollama)

```bash
# install from https://ollama.com, then:
ollama pull llama3.2
ollama serve            # usually already running as a background service
```

The sidebar shows 🟢 *Ollama online* or ℹ️ *offline → rule-based mentor*. Nothing breaks if Ollama is absent: the chatbot answers with deterministic, still-personalised rules. Override with `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.

### Optional: ChromaDB semantic matching

The default matcher is TF-IDF + cosine similarity (offline, zero setup). To use a real vector store:

```bash
pip install chromadb
ollama pull nomic-embed-text
export SEMANTIC_BACKEND=auto      # or "chroma"; falls back to TF-IDF if anything is missing
```

Embeddings come from Ollama (Chroma's default embedder would download a model from the internet).

### Configuration

All settings are environment variables (see `.env.example`). The app reads real environment variables and does not auto-load `.env`; export them in your shell. There are no API keys or secrets.

---

## 🧮 Scoring model

| Component | Weight | Rule |
|---|---:|---|
| Skills match | 35 | 85% required-skill coverage + 15% preferred-skill coverage (role-specific) |
| Projects | 20 | `projects / 4`, capped at 1 |
| Academics | 15 | 60% CGPA (5.0 → 0, 10 → 1) + 40% aptitude score |
| Soft skills | 15 | communication score / 100 |
| Experience | 10 | `internships / 2`, capped at 1 |
| Certifications | 5 | `certifications / 3`, capped at 1 |

**Worked example** (Data Analyst): skills Python, SQL, Excel (3/7 required) → 12.75; 2 projects → 10; CGPA 7.5 and aptitude 50 → 7.5; communication 60 → 9; 1 internship → 5; 1 cert → 1.7. Total **45.9 → Needs work**.

Every number is visible in the *Why this score* tab, the chart, the report and the mentor's context.

---

## 🎬 3-minute demo script

| Time | Do | Say |
|---|---|---|
| **0:00-0:20** | Open the app and show the sidebar (80 students, Ollama status). | "Students get a number but no plan. We turn a role-specific readiness score into a concrete action plan, and give the placement cell the campus view." |
| **0:20-1:05** | **Student tab**: pick a student, then point at the gauge, breakdown chart and *Why this score* table. Switch the role from Data Analyst to ML Engineer. | "The score is explainable: weights 35/20/15/15/10/5. The same student scores differently per role because skills are matched against role requirements." |
| **1:05-1:40** | **Skill gaps** and **Action plan** tabs: open the top action, then the weekly timeline. Use **What-if**: add 2 skills and 1 project. | "Each missing skill has specific learning steps, a mini-project, an hours estimate and a points impact. The what-if shows the score jumping from Almost ready to Ready." |
| **1:40-2:10** | **Resume Analyzer**: click *Load sample resume* (or upload a PDF). Show the extracted skills, the profile estimates, and the score. Scroll to semantic job matches. | "Paste or upload a PDF: skills are extracted offline, the profile is pre-filled, and we score it. Semantic matching ranks sample internship postings against the resume." |
| **2:10-2:40** | **Placement Dashboard**: KPIs, department chart, top skill gaps, at-risk table, click CSV export. Switch to *One role for everyone*. | "The placement officer sees average readiness, % ready, which department lags, and the one skill to teach in a campus workshop. At-risk students export to CSV." |
| **2:40-3:00** | **AI Mentor**: click *What should I learn first?* then type *How do I learn SQL?*. Mention the fallback. Download the PDF report. | "The mentor is grounded in the student's score and gaps. Ollama llama3.2 when available, a rule-based engine when not, so the demo never fails. Reports download as Markdown or PDF." |

**Backup lines:** *"All data is synthetic."* · *"Scoring is a pure function with unit tests."* · *"No internet and no API keys needed."*

---

## 🧪 Tests

```bash
pytest -v
```

- `tests/test_scoring.py`: perfect profile = 100, empty/garbage input = 0 without crashing, exact weighted maths and role-specificity, level boundaries, alias normalisation.
- `tests/test_pipeline.py`: 80 unique seeded students, analytics (including empty frames), resume parsing and PDF round-trip, mentor fallback when Ollama is down, semantic ranking.

---

## 💡 Ideas to extend (for judges)

1. **Live job-feed matching:** ingest real postings (RSS or CSV), embed them and recommend internships with a "you are 2 skills away" badge.
2. **Cohort interventions:** auto-group at-risk students by shared gap and generate a workshop plan and invite list for the placement cell.
3. **Progress tracking:** store assessments over time (a new `assessments` table) and chart score trajectories and plan completion.
4. **Mock-interview agent:** use the local LLM to run role-specific interviews, score answers with a rubric and feed the result into the soft-skills component.
5. **Fairness and calibration:** back-test the weights against real placement outcomes, add a logistic-regression "placement probability" next to the heuristic score, and audit gaps by department and gender.

---

## 🩺 Troubleshooting

- **`ModuleNotFoundError: readiness`**: run commands from the `internship-readiness-checker/` folder.
- **PDF says "No selectable text"**: the PDF is a scan; paste the text instead.
- **Mentor shows "rule-based"**: Ollama is not running or the model is not pulled (`ollama pull llama3.2`).
- **Want a fresh dataset**: delete `data/readiness.db` or press **Regenerate synthetic data** in the sidebar.

_All student data in this prototype is synthetic. Scores are guidance, not hiring decisions._
