"use client";

export type Candidate = { text: string; readers: string[] };
export type ReviewItem = {
  id: string;
  block: number;
  tok_from: number;
  tok_to: number;
  candidates: Candidate[];
  word_boxes: number[][];
  line_boxes: number[][];
  decision: string | null;
};
export type SpotItem = {
  id: string;
  tok: number;
  text: string;
  word_boxes: number[][];
  line_boxes: number[][];
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

export function cropUrl(pid: string, lineBoxes: number[][], wordBoxes: number[][]) {
  const boxes = lineBoxes.length ? lineBoxes : wordBoxes;
  if (!boxes.length) return null;
  const x0 = Math.min(...boxes.map((b) => b[0]));
  const y0 = Math.min(...boxes.map((b) => b[1]));
  const x1 = Math.max(...boxes.map((b) => b[2]));
  const y1 = Math.max(...boxes.map((b) => b[3]));
  const hl = wordBoxes.map((b) => b.join(",")).join(";");
  const q = new URLSearchParams({
    x0: String(x0),
    y0: String(y0),
    x1: String(x1),
    y1: String(y1),
    hl,
    t: getToken(),
  });
  return `/api/review/gold/${pid}/crop?${q}`;
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
