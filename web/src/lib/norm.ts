// Client-side mirror of pipeline/normalize.py (level "search"), used only for matching
// quotes to blocks in the UI. Never used to alter displayed text.
const DIAC = /[ؐ-ًؚ-ٰٟۖ-ۭـ]/g;
const MARK = /\(\s*[\d٠-٩]{1,3}\s*\)/g;

export function norm(s: string): string {
  return s
    .normalize("NFKC")
    .replace(MARK, " ")
    .replace(DIAC, "")
    .replace(/[أإآٱ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي")
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)))
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/ء/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Ids of the blocks whose text contains the quote (or most of its words). */
export function blocksForQuote<T extends { id: string; text: string }>(blocks: T[], quote: string): string[] {
  const q = norm(quote);
  if (!q) return [];
  const exact = blocks.filter((b) => norm(b.text).includes(q)).map((b) => b.id);
  if (exact.length) return exact;
  const words = q.split(" ");
  let best: { id: string; score: number } | null = null;
  for (const b of blocks) {
    const bw = new Set(norm(b.text).split(" "));
    const score = words.filter((w) => bw.has(w)).length / words.length;
    if (!best || score > best.score) best = { id: b.id, score };
  }
  return best && best.score >= 0.6 ? [best.id] : [];
}
