# Quran reference text

**Primary:** Quranpedia.net official data dump, version 2026-09-30/2026-10-02.
- `qp_mushafs-1.json.gz` — «مصحف حفص»: "القرآن الكريم برواية حفص عن عاصم، موافق لطبعة مجمع الملك فهد لطباعة المصحف الشريف". 114 surahs, 6236 ayahs.
- `qp_mushafs-2.json.gz` — «مصحف حفص نسخة نصية» (King Fahd Complex Uthmani script, text edition). Kept for display experiments.
- Source: https://api.quranpedia.net/dumps (manifest saved as `qp_manifest.json`).
- License: free use in apps; republishing the data requires crediting Quranpedia.net with a link and the dump version (full license text is embedded in each file). Content is continuously corrected; re-sync via `https://quranpedia.net/api/v1/changes?since=<version>`.

**Why this source:** the challenge scientific package (p.3) names the approved Quran text as «طبعة مجمع الملك فهد أو الواردة في quranpedia.net». Mushaf 1 is both. We tried the King Fahd Complex sites directly on Oct 4: the "Hafs AI" package (dm.qurancomplex.gov.sa, 1441-AI-hafs.zip) contains only Adobe Illustrator page artwork, not text, and fonts.qurancomplex.gov.sa offers fonts only.

**Fallback (documented, not used unless primary fails):** Tanzil Uthmani / Simple-Clean (tanzil.net, CC BY 3.0, text must not be modified).

The printed text in the book is NEVER rewritten from this reference; the reference is only displayed alongside it, clearly labeled.
