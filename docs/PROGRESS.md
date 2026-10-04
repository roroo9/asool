# Progress

Deadline: **Tue Oct 6, 2026, 23:59 Riyadh time**. Target submission-ready: **Tue 18:00**.

## Time plan (Riyadh time)
| Phase | Planned window | Status |
|---|---|---|
| 0 Setup | Sun Oct 4, 07:00–09:00 | Done, waiting for GATE 0 approval |
| 1 Model bake-off (3 pages) | Sun 09:00–13:00 | Needs API keys |
| 2 Full ingestion (30 pages) + baseline | Sun 13:00–22:00 | |
| 3 API | Mon Oct 5, 08:00–14:00 | |
| 4 Frontend + preview deploy | Mon 14:00 – Tue 08:00 | |
| 5 Evaluation & hardening | Tue Oct 6, 08:00–14:00 | |
| 6 Ship | Tue 14:00–18:00 | |
| Buffer | Tue 18:00–23:59 | |

Human tasks running in parallel: correct the gold set (Sun evening to Mon), verify eval questions (Mon).

## Phase 0: done
- Repo skeleton, `uv` Python env (Python 3.13), FastAPI `/health`, Next.js 16 app (RTL Arabic, Amiri + IBM Plex Sans Arabic).
- `pipeline/normalize.py` with unit tests.
- `.env.example`, `.gitignore` (book PDFs and page images excluded).
- Book files downloaded. Edition check done.

## Decisions and findings
- **Edition:** `rs-mohaqaq.pdf` is the 1956 دار إحياء الكتاب العربي edition (title page credits مصطفى محمد عمارة). `rs.pdf` is دار الريان 1987 and is not used.
- **Page numbering:** PDF page N (1-based) shows printed page N. No offset.
- **Corpus:** printed pages 12–41 (30 pages). باب الإخلاص starts p.12, باب التوبة p.18, باب الصبر p.30.
- **archive.org text layer is unusable.** Both `rs-mohaqaq_text.pdf` and `rs-mohaqaq_djvu.txt` contain Latin junk (0% Arabic characters). archive.org ran OCR without Arabic. Decision: the baseline uses our own Tesseract 5 `ara` run (allowed by spec §5.1: "else Tesseract ara plain text"). The gold draft will come from Tesseract `ara` + a second VLM, then a human corrects it.
- **Bake-off pages (proposed):** p.41 (many footnotes, including a long commentary footnote), p.30 (start of باب الصبر, many Quran verses), p.20 (dense text).

## Known issues
- None blocking yet.
