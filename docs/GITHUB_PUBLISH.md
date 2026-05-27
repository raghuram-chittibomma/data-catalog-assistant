# Publishing a clean GitHub repo

Use this checklist before linking the project on a resume.

---

## 1. Create the repository

```powershell
cd C:\Users\raghu\AI-Projects\data-catalog-assistant
git init
git add .
git status   # verify no .env, chroma_data/, secrets
git commit -m "Initial commit: Data Catalog Assistant POC"
git remote add origin https://github.com/raghuram-chittibomma/data-catalog-assistant.git
git branch -M main
git push -u origin main
```

Repository name: **`data-catalog-assistant`** (matches UI title **Data Catalog Assistant**).

---

## 2. Pre-push verification

| Check | Command / action |
|-------|------------------|
| No secrets in git | `git status` must not list `.env`; run `git grep -i "sk-"` (empty or `.env.example` only) |
| Ignore local data | `.gitignore` includes `.env`, `chroma_data/`, `logs/` |
| Config | No hosts/passwords in committed `config.yaml` — use `${DW_HOST}`, `${METADATA_DB_HOST}`, etc. |
| Tests pass | `conda activate ai-dev` then `pytest tests/ -q` |
| README badge | Points to [raghuram-chittibomma/data-catalog-assistant](https://github.com/raghuram-chittibomma/data-catalog-assistant) |
| Screenshots | Four PNGs in [images/](images/) |
| LICENSE | [MIT](../LICENSE) at repo root |

---

## 3. GitHub repository settings

- **Description:** `RAG data catalog POC — lineage, impact analysis, NL→SQL (Python, Postgres, Chroma, FastAPI, Gradio)`
- **Topics:** `rag`, `data-catalog`, `lineage`, `chromadb`, `fastapi`, `gradio`, `postgresql`, `python`

---

## 4. CI

Workflow: [.github/workflows/ci.yml](../.github/workflows/ci.yml) — confirm green under **Actions** after push.

---

## 5. Resume / LinkedIn

`https://github.com/raghuram-chittibomma/data-catalog-assistant`

Point to **README** (overview + screenshots) and **docs/SHOWCASE.md** (design narrative).

---

## 6. What not to publish

- `.env` with API keys or DB passwords
- `chroma_data/` (regenerate via refresh job)
- Private host IPs unless intentional — document env vars instead

---

## Monorepo note

If this project stays under `AI-Projects`, add to the parent README:

```markdown
## Data Catalog Assistant
See [data-catalog-assistant/](data-catalog-assistant/) — RAG-based warehouse catalog POC.
```

For resumes, a **standalone** repo (step 1) is still cleaner.
