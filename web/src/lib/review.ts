"use client";

export type Candidate = { text: string; readers: string[] };
export type Loc = "word" | "approx" | "gap" | "uncertain";
export type Located = {
  loc: Loc;
  word_boxes: number[][];
  line_boxes: number[][];
  hint_box: number[] | null;
};
export type ReviewItem = Located & {
  id: string;
  block: number;
  tok_from: number;
  tok_to: number;
  candidates: Candidate[];
  decision: string | null;
  previous_decision?: string;
  requeued?: string;
};
export type SpotItem = Located & {
  id: string;
  tok: number;
  text: string;
  verdict: "ok" | "wrong" | null;
  fix: string | null;
};
export type DraftBlock = {
  order: number;
  type: string;
  author_role: string;
  footnote_marker: string;
  text: string;
  type_reader_c: string | null;
  type_confirmed: string | null;
};
export type Progress = {
  page_id: string;
  printed: number;
  items_total: number;
  items_done: number;
  spot_total: number;
  spot_done: number;
  structure_reviewed: boolean;
  finalized: boolean;
  auto_accepted: number;
  total_tokens: number;
};
export type Draft = {
  page_id: string;
  printed: number;
  blocks: DraftBlock[];
  tokens: { block: number; raw: string }[];
  review_items: ReviewItem[];
  spotcheck: SpotItem[];
  progress: Progress;
};

const LS_TOKEN = "asool.reviewToken";
const LS_NAME = "asool.reviewer";

function ls(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}
export function getToken() {
  // A shared link may carry the access code as ?code=...; remember it for this browser.
  if (typeof window !== "undefined") {
    const code = new URLSearchParams(window.location.search).get("code");
    if (code) {
      try {
        localStorage.setItem(LS_TOKEN, code);
      } catch {
        return code;
      }
    }
  }
  return ls(LS_TOKEN);
}
export function getReviewer() {
  return ls(LS_NAME);
}
export function saveIdentity(token: string, name: string) {
  try {
    localStorage.setItem(LS_TOKEN, token);
    localStorage.setItem(LS_NAME, name);
  } catch {
    /* private mode: values live for this tab only */
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/review/gold${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "content-type": "application/json",
      "x-review-token": getToken(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(res.status === 401 ? "رمز المراجعة غير صحيح" : msg);
  }
  return res.json() as Promise<T>;
}

const boxParam = (bs: number[][]) => bs.map((b) => b.join(",")).join(";");

/** Crop of the full printed line(s) containing the disputed words (null if not located). */
export function cropUrl(pid: string, x: Located): string | null {
  if (x.loc === "uncertain" || !x.line_boxes.length) return null;
  const y0 = Math.min(...x.line_boxes.map((b) => b[1]), ...x.word_boxes.map((b) => b[1]));
  const y1 = Math.max(...x.line_boxes.map((b) => b[3]), ...x.word_boxes.map((b) => b[3]));
  const q = new URLSearchParams({
    y0: String(y0),
    y1: String(y1),
    hl: boxParam(x.word_boxes),
    t: getToken(),
  });
  return `/api/review/gold/${pid}/crop?${q}`;
}

/** Whole page with the disputed words (or the uncertain area) marked. */
export function pageUrl(pid: string, x: Located): string {
  const q = new URLSearchParams({
    hl: boxParam(x.word_boxes),
    hint: x.hint_box ? x.hint_box.join(",") : "",
    t: getToken(),
  });
  return `/api/review/gold/${pid}/page?${q}`;
}

export const BLOCK_TYPES: Record<string, string> = {
  heading: "عنوان",
  body: "متن",
  hadith: "نص حديث",
  quran: "آية",
  footnote: "حاشية",
  editor_commentary: "تعليق المحقق",
  poetry: "شعر",
  page_number: "رقم الصفحة",
  page_header: "ترويسة",
  marginalia: "هامش جانبي",
  other: "أخرى",
};

export const toArabicDigits = (n: number | string) =>
  String(n).replace(/\d/g, (d) => "٠١٢٣٤٥٦٧٨٩"[Number(d)]);
