# Screenshot guide (portfolio / README)

Add four PNG or WebP files here (1280×720 or similar). The main [README.md](../../README.md) references these paths.

## How to capture

1. Run `python batch_jobs/run_refresh_job.py` then `python src/main.py`.
2. Open http://127.0.0.1:7860
3. Use Windows **Snipping Tool** or **Win+Shift+S** (save into this folder).

## Required files

| File | Tab / action | What to show |
|------|----------------|--------------|
| `catalog-search.png` | **Catalog search · Embeddings** | Query e.g. `product revenue by category` with 3–5 results |
| `lineage.png` | **Lineage · Metadata** | `public.orders`, direction **both**, ASCII diagram visible |
| `change-impact.png` | **Impact · Metadata** | Asset id `public.orders`, change text `Rename column company_name to legal_name on public.customers` — header should say **public.customers** and show the resolution note |
| `generate-sql.png` | **Generate SQL · LLM** | Show the **LLM provider** radio (**Local (Ollama)** preferred for portfolio), NL query e.g. `top 5 customers by order count`, waiting/status if useful, then SQL with **LLM:** `ollama · qwen3:8b` (or OpenAI) line visible |

## Optional

| File | Content |
|------|---------|
| `ui-legend.png` | Top of page: “What uses AI in this demo?” legend |
| `catalog-browse.png` | Catalog browse summary with table counts |

After adding images, commit them:

```powershell
git add docs/images/*.png
git commit -m "Add portfolio screenshots for README"
```

Do **not** commit `.env`, `chroma_data/`, or database dumps.
