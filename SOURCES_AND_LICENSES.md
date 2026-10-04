# Sources and Licenses

Every book, dataset, font, model and library used by Asool, with its license and how we use it.
This file is kept honest: unknown or unverified status is written as such.

## Books

### رياض الصالحين (Riyad al-Salihin)
| Field | Value |
|---|---|
| Author | الإمام يحيى بن شرف النووي (ت 676هـ) |
| Edition used | دار إحياء الكتاب العربي، القاهرة، 1375هـ / 1956م |
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

Shamela: not used (different edition, page numbers would not match).

## Reference data
| Item | License | Use |
|---|---|---|
| Tanzil Quran text (Uthmani, Simple-Clean) | Tanzil license: free to copy with attribution, text must not be modified | Quran verse verification. To be added in Phase 2. |
| quranpedia.net | Outbound links only | Surah/ayah reference links |
| dorar.net | Outbound search links only, no scraping | "Check this hadith" link |

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

## AI models (filled in after Phase 1 bake-off)
To be recorded with exact model IDs and the date of each provider's pricing page.
