export type Rect = number[]; // [x0, y0, x1, y1] in 300-DPI page pixels

export type Block = {
  id: string;
  page_id: string;
  type: string;
  author_role: string | null;
  text: string;
  bbox: Rect | null;
  rects: Rect[];
  bbox_source: string;
  confidence: number;
  flags: string[];
  footnote_marker: string | null;
  attached_to: string | null;
};

export type FootnoteLink = {
  id?: number;
  page_id: string;
  marker: string;
  anchor_block_id: string | null;
  anchor_char_offset: number | null;
  footnote_block_id: string;
  confidence: number;
  method: string;
};

export type DiffOp = { op: string; printed: string[]; reference: string[]; at: number };

export type QuranRef = {
  block_id: string;
  surah: number;
  ayah_start: number;
  ayah_end: number;
  match_type: "exact" | "minor_variant" | "mismatch";
  similarity: number;
  printed_text: string;
  canonical_text: string;
  diff_ops: DiffOp[];
  reference_source: string;
  quranpedia_url?: string;
};

export type Hadith = {
  id: string;
  narrator: string | null;
  takhrij_printed: string | null;
  grading_status: string;
  grading: string;
  grading_source: string | null;
  grading_source_url: string | null;
  dorar_search_url: string;
  block_ids?: string[];
};

export type PageRef = { id: string; printed: number; citation?: string };

export type Passage = {
  id: string;
  kind: "matn" | "editor_commentary" | "baseline";
  author_role?: string;
  author_label?: string;
  breadcrumb?: string[];
  text: string;
  highlights?: number[][];
  pages: PageRef[];
  blocks?: Block[];
  footnotes?: (Block & { attached_text: string[]; marker_links: FootnoteLink[] })[];
  quran?: QuranRef[];
  hadith?: Hadith[];
  commentary_on?: string | null;
  min_confidence?: number;
  retrieval?: { score?: number; rrf?: number; bm25_rank: number | null; dense_rank: number | null; dense_sim: number | null };
  note?: string;
};

export type PageData = {
  id: string;
  printed: number;
  width: number;
  height: number;
  image: string;
  citation: string;
  coverage: number;
  uncovered_regions: { bbox: Rect; lines: string[] }[];
  blocks: Block[];
  footnote_links: FootnoteLink[];
  quran: QuranRef[];
  hadith: Hadith[];
  prev: string | null;
  next: string | null;
};

export type VerseCandidate = {
  surah: number;
  surah_name: string;
  ayah_start: number;
  ayah_end: number;
  canonical_text: string;
  similarity: number;
  quranpedia_url: string;
  in_corpus_pages: number[];
};

export type SourcePoint = { text: string; passage: string; quote: string; verified?: boolean; passage_id?: string };

export type AnswerRes = {
  question: string;
  status: "answered" | "abstained" | "referral" | "unavailable";
  language: string;
  level: string | null;
  message?: string;
  answer?: { source_points: SourcePoint[]; explanation: string; disagreement_noted: boolean };
  verification?: { total: number; verified: number; removed: unknown[] };
  quoted_verse_check?: {
    printed_in_question: string;
    exact: boolean;
    candidates: VerseCandidate[];
    note_ar: string;
    reference_source: string;
  } | null;
  passages: Passage[];
  stages?: { stage: string; [k: string]: unknown }[];
  model?: string;
  cached?: boolean;
  ai_notice?: string;
  abstain_reason?: string;
};

export const BOOK_ID = "riyad1956";
export const pageNum = (pid: string) => Number(pid.split("-p")[1]);
