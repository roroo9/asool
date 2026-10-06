# Sources and Licenses

Every book, dataset, font, model and library used by Asool, with its license and how we use it.
This file is kept honest: unknown or unverified status is written as such.

## Books

### رياض الصالحين (Riyad al-Salihin)
| Field | Value |
|---|---|
| Author | الإمام يحيى بن شرف النووي (ت 676هـ) |
| Edition used | دار إحياء الكتب العربية (عيسى البابي الحلبي)، القاهرة، 1375هـ / 1956م |
| Edition evidence | Title page: editor مصطفى محمد عماره, city القاهرة, and the press emblem "مطبعة دار إحياء الكتب العربية – عيسى البابي الحلبي". The emblem date (1336هـ/1918م) is the press founding year. **The printing year 1375هـ/1956م is not printed in the scan**; it comes from the archive.org item description. |
| Word meanings explained by | مصطفى محمد عمارة |
| Source page | https://archive.org/details/rsnawwy |
| File used | `rs-mohaqaq.pdf` (scanned images), plus `rs-mohaqaq_text.pdf` (archive.org OCR text layer) |
| File NOT used | `rs.pdf` (دار الريان 1987). Downloaded only to tell the two editions apart. |
| Selected by | A human (project owner). The agent did not search for or choose the book. |
| Corpus | Printed pages 12–41 (PDF pages 12–41 counting from 1): باب الإخلاص، باب التوبة، and the first part of باب الصبر. |

**License status**
- **Matn (Imam al-Nawawi's text):** public domain (author died 676 AH).
- **Footnotes and word explanations by مصطفى محمد عمارة, and the 1956 typesetting:** copyright status **unverified**. We could not confirm the editor's death date or any public-domain dedication.
- **Consequence:** the PDF files and rendered page images are **excluded from the public GitHub repository** (see `.gitignore`). Page images are served only from the live deployment, for the purpose of showing citations. Extracted text snippets in the repo are limited to what the evaluation and index need.
- **archive.org text layer:** we inspected it and found it unusable (Arabic was decoded as Latin characters, 0% Arabic). So the baseline uses our own Tesseract `ara` run instead. See `docs/PROGRESS.md`.

Shamela: used only as an independent text cross-check during gold review (different edition; page numbers do not match). See Reference data.

## Reference data
| Item | License / terms | Use |
|---|---|---|
| King Fahd Glorious Quran Printing Complex, developer data, Hafs v3.0 (qurancomplex.gov.sa/quran-dev, `kfgqpc_hafs_v30.zip`) | Published by the Complex for developers; redistribution terms not stated, so the file is downloaded at build time and not committed | **Primary** Quran reference: display text (Uthmani) + matching text (imla'i) |
| Quranpedia.net dump, mushaf 1 (Hafs, matching the King Fahd print), version 2026-09-30 | Free in apps; republishing the data requires credit + link + version | Documented fallback Quran reference |
| quranpedia.net | Outbound links | Surah/ayah link for every verified verse |
| Shamela (shamela.ws), book 2348 «رياض الصالحين» ت. ماهر الفحل، دار ابن كثير 1428هـ (the editor made it free) | Text fetched for review only (pages 10–90, 1 req/s), not redistributed | Independent text cross-check during gold review |
| dorar.net hadith search API (dorar.net/article/389) | Official public API | Hadith grading for non-Sahihayn hadiths. Blocked from our machine on Oct 4 (Cloudflare); see CLAUDE.md §12.D |
| HadeethEnc API (hadeethenc.com/api/v1) | Official public API | Second hadith reference (attribution + grade) |
| QuranEnc API (quranenc.com/api/v1), «التفسير الميسر» (King Fahd Complex), key `arabic_moyassar` | Official public API of an approved platform (scientific package p.9); downloaded at build time by `scripts/fetch_tafsir.py`, not committed | Meaning of every verified verse, attributed and linked; never generated |
| Encyclopedia of Translated Islamic Terminology (terminologyenc.com/api/v1) | Official public API of an approved platform (package p.9); 17 entries stored with their source links in `data/reference/terminologyenc/terms.json` | Definitions for foundational questions and term translations, labeled as outside the indexed book |
| «بينات: أسئلة وأجوبة عن الإسلام» (dawa.center/file/7937), dorar.net | Links only | Referrals for foundational questions, as recommended by the package |
| Jamhara (islamic-content.com/dictionary), terminologyenc.com | Public reference | English equivalents of Islamic terms |

## Fonts (all SIL Open Font License 1.1)
| Font | Use |
|---|---|
| IBM Plex Sans Arabic | UI text |
| Amiri | Source (book) text |
| Amiri Quran | Quran text (Phase 4) |

## Software
| Tool | License | Use |
|---|---|---|
| Tesseract OCR + `ara` traineddata | Apache 2.0 | Geometry lane, baseline OCR |
| PyMuPDF | AGPL-3.0 | Rasterizing PDF pages |
| FastAPI, Pydantic, uvicorn | MIT / BSD | API |
| rapidfuzz | MIT | Fuzzy alignment |
| jiwer | Apache 2.0 | CER / WER |
| numpy | BSD | Vector search |
| Next.js, React | MIT | Web app |
| Tailwind CSS | MIT | Styling |

## AI models and OCR engines
| Model / engine | Provider / license | Role |
|---|---|---|
| Gemini 3.1 Pro (preview), `google/gemini-3.1-pro-preview` | Google, via OpenRouter (paid) | Asool page parser (prompt `page_parse.v2`) |
| Gemini 3.8 Flash, Gemini 3.5 Flash | Google, via OpenRouter / Google AI Studio free tier | Parser fallbacks; bake-off candidates |
| Gemini Embedding 2, `google/gemini-embedding-2` | Google, via OpenRouter (paid) | Dense retrieval embeddings |
| Claude Opus 5.5, Claude Fable 5.1 | Anthropic API (paid) | Independent gold-set readers B and C (not used in the product) |
| Surya OCR 2 (`surya-ocr` 0.22.1, model `datalab-to/surya-ocr-2`) | Open source (code GPL-3.0; model weights under Datalab's model license), run locally via llama.cpp | Gold-set Reader C on 12 pages |
| Tesseract 5.5.3 + `ara` traineddata | Apache 2.0 | Gold Reader A, geometry lane (word/line boxes), baseline OCR |
| GPT-5.6 Terra, Qwen3-VL 32B | via OpenRouter | Bake-off candidates only |

Pricing used for cost reports: OpenRouter per-call reported cost; Anthropic model table dated 2026-09-25.
