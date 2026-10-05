"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getReviewer, getToken, toArabicDigits } from "@/lib/review";

type Cit = { id: string; kind: string; pages: number[]; excerpt: string; required?: boolean };
type Fields = {
  question: string;
  expected_behavior: string;
  gold_chunk_ids: string[] | null;
  required_chunk_ids: string[] | null;
};
type Draft = Fields & {
  type: string;
  allowed_behaviors?: string[] | null;
  notes?: string | null;
  expected_ar?: string | null;
  expected_verses?: string[] | null;
};
type Review = { action: "approve" | "edit" | "remove"; reviewer: string; note: string; edit: Partial<Fields>; decided_at: string };
type Item = {
  id: string;
  official_no: number | null;
  draft: Draft;
  citations: Cit[];
  proposal: (Partial<Fields> & { why: string; by: string; citations: Cit[] }) | null;
  review: Review | null;
};
type Listing = { items: Item[]; chunks: Cit[]; progress: { done: number; total: number } };

const BEH: Record<string, string> = {
  answer: "إجابة موثقة",
  abstain: "امتناع مع أقرب النصوص",
  refer: "إحالة إلى أهل العلم",
  correct_verse: "تصحيح نص الآية",
};
const TYPES: Record<string, string> = {
  direct: "سؤال مباشر",
  needs_footnote: "يحتاج إلى الحاشية",
  cross_page: "يمتد عبر صفحتين",
  multi_condition: "عدة شروط أو أدلة",
  editor_commentary: "تعليق المحقق",
  quran: "آيات",
  english: "سؤال بالإنجليزية",
  unanswerable: "خارج الصفحات المفهرسة",
  personal_case: "حالة شخصية (المستوى د)",
  hostile: "صياغة عدائية",
  misquoted_verse: "آية محرفة في السؤال",
  official: "حالة رسمية",
};
const ACT: Record<string, string> = { approve: "اعتُمد", edit: "عُدِّل", remove: "حُذف" };

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`/api/review/questions${path}`, {
    method,
    headers: { "content-type": "application/json", "x-review-token": getToken() },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = await res.text();
    try {
      msg = JSON.parse(msg).detail ?? msg;
    } catch {
      /* plain text */
    }
    throw new Error(res.status === 401 ? "رمز المراجعة غير صحيح" : String(msg));
  }
  return res.json() as Promise<T>;
}

const reviewer = () => getReviewer() || "rawan";
const pagesAr = (ps: number[]) => ps.map((p) => toArabicDigits(p)).join("، ");

function Citations({ cits, empty }: { cits: Cit[]; empty: string }) {
  if (!cits.length) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className="grid gap-2">
      {cits.map((c) => (
        <li key={c.id} className="rounded-md border border-line bg-paper/60 p-2">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded border border-thread/60 px-1.5 py-0.5 text-thread-strong">ص {pagesAr(c.pages)}</span>
            <span className="text-muted">{c.kind === "editor_commentary" ? "تعليق المحقق" : "متن الإمام النووي"}</span>
            {c.required && <span className="rounded bg-insight/15 px-1.5 py-0.5 text-insight">يجب الاستشهاد به</span>}
            <span className="text-muted" dir="ltr">{c.id.replace("riyad1956-", "")}</span>
          </div>
          <p className="source-text mt-1 leading-loose">{c.excerpt} …</p>
        </li>
      ))}
    </ul>
  );
}

function Editor({ item, chunks, onSave, onCancel }: { item: Item; chunks: Cit[]; onSave: (e: Partial<Fields>) => void; onCancel: () => void }) {
  const d = item.draft;
  const [question, setQuestion] = useState(d.question);
  const [beh, setBeh] = useState(d.expected_behavior);
  const [gold, setGold] = useState<string[]>(d.gold_chunk_ids ?? []);
  const [req, setReq] = useState<string[]>(d.required_chunk_ids ?? []);
  const [add, setAdd] = useState("");
  const byId = useMemo(() => Object.fromEntries(chunks.map((c) => [c.id, c])), [chunks]);
  const toggleReq = (id: string) => setReq((r) => (r.includes(id) ? r.filter((x) => x !== id) : [...r, id]));
  return (
    <div className="mt-3 grid gap-3 rounded-lg border border-insight/40 bg-insight/5 p-3 text-sm">
      <label className="grid gap-1">
        <span className="font-medium">نص السؤال</span>
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} className="rounded border border-line bg-surface p-2" />
      </label>
      <label className="grid gap-1">
        <span className="font-medium">السلوك المتوقع</span>
        <select value={beh} onChange={(e) => setBeh(e.target.value)} className="rounded border border-line bg-surface p-2">
          {Object.entries(BEH).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <div className="grid gap-1">
        <span className="font-medium">المصادر الصحيحة</span>
        {gold.length === 0 && <span className="text-muted">لا توجد مصادر.</span>}
        {gold.map((id) => (
          <div key={id} className="flex flex-wrap items-center gap-2 rounded border border-line bg-surface p-2">
            <span className="source-text flex-1">
              ص {pagesAr(byId[id]?.pages ?? [])}: {byId[id]?.excerpt.split(" ").slice(0, 14).join(" ")} …
            </span>
            <label className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={req.includes(id)} onChange={() => toggleReq(id)} /> يجب الاستشهاد به
            </label>
            <button
              className="rounded border border-line px-2 py-0.5 text-xs"
              onClick={() => {
                setGold((g) => g.filter((x) => x !== id));
                setReq((r) => r.filter((x) => x !== id));
              }}
            >
              إزالة
            </button>
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <select value={add} onChange={(e) => setAdd(e.target.value)} className="min-w-0 flex-1 rounded border border-line bg-surface p-2">
            <option value="">إضافة مصدر من الكتاب…</option>
            {chunks
              .filter((c) => !gold.includes(c.id))
              .map((c) => (
                <option key={c.id} value={c.id}>
                  ص {pagesAr(c.pages)}: {c.excerpt.split(" ").slice(0, 10).join(" ")}
                </option>
              ))}
          </select>
          <button
            className="rounded border border-line px-3 py-1"
            disabled={!add}
            onClick={() => {
              setGold((g) => [...g, add]);
              setAdd("");
            }}
          >
            إضافة
          </button>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          className="rounded bg-ink px-3 py-1.5 text-paper"
          onClick={() => onSave({ question, expected_behavior: beh, gold_chunk_ids: gold, required_chunk_ids: req })}
        >
          حفظ التعديل
        </button>
        <button className="rounded border border-line px-3 py-1.5" onClick={onCancel}>
          إلغاء
        </button>
      </div>
    </div>
  );
}

function Card({ item, chunks, onDone }: { item: Item; chunks: Cit[]; onDone: () => void }) {
  const [note, setNote] = useState(item.review?.note ?? "");
  const [editing, setEditing] = useState(false);
  const [err, setErr] = useState("");
  const d = item.draft;
  const send = (action: Review["action"], edit?: Partial<Fields>) =>
    call(`/${item.id}`, "POST", { action, reviewer: reviewer(), note, edit })
      .then(() => {
        setEditing(false);
        onDone();
      })
      .catch((e: Error) => setErr(e.message));
  const r = item.review;
  return (
    <li id={item.id} className={`rounded-xl border p-4 ${r ? "border-line bg-surface/60" : "border-line bg-surface"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted" dir="ltr">
          {item.id}
        </span>
        {item.official_no != null && (
          <span className="rounded bg-thread/20 px-2 py-0.5 font-medium text-thread-strong">
            الحالة الرسمية رقم {toArabicDigits(item.official_no)} من الحزمة العلمية
          </span>
        )}
        <span className="rounded border border-line px-2 py-0.5">{TYPES[d.type] ?? d.type}</span>
        <span className="rounded border border-line px-2 py-0.5">
          المتوقع: {(d.allowed_behaviors ?? [d.expected_behavior]).map((b) => BEH[b] ?? b).join(" أو ")}
        </span>
        {r && (
          <span className={`ms-auto rounded px-2 py-0.5 font-medium ${r.action === "remove" ? "bg-madder/15 text-madder" : "bg-thread/20 text-thread-strong"}`}>
            ✓ {ACT[r.action]} · {r.reviewer}
          </span>
        )}
      </div>
      <p className="mt-2 text-lg font-medium" dir="auto">
        {r?.edit?.question ?? d.question}
      </p>
      {d.expected_ar && <p className="mt-1 text-sm text-muted">ما تطلبه الحزمة: {d.expected_ar}</p>}
      <div className="mt-3">
        <p className="mb-1 text-sm font-medium">المصادر الصحيحة في الكتاب</p>
        {d.expected_verses?.length ? (
          <p className="mb-2 text-sm">
            الآيات الصحيحة المتوقع عرضها:{" "}
            {d.expected_verses.map((v) => {
              const [s, a] = v.split(":");
              return `سورة ${toArabicDigits(Number(s))}: ${toArabicDigits(Number(a))}`;
            }).join("، ")}{" "}
            <span className="text-muted">(من مصحف مجمع الملك فهد)</span>
          </p>
        ) : null}
        <Citations
          cits={item.citations}
          empty={
            d.expected_behavior === "answer"
              ? "لا توجد مصادر محددة."
              : d.expected_behavior === "correct_verse"
                ? "لا يُشترط الاستشهاد بمقطع من الكتاب."
                : "لا يُنتظر الاستشهاد بمصدر: السلوك المتوقع امتناع أو إحالة."
          }
        />
      </div>
      {item.proposal && !r && (
        <div className="mt-3 rounded-lg border border-amber/60 bg-amber/10 p-3 text-sm">
          <p className="font-medium">تعديل مقترح من الوكيل (يحتاج اعتمادك)</p>
          <p className="mt-1">{item.proposal.why}</p>
          <p className="mt-2 font-medium">المصادر بعد التعديل:</p>
          <div className="mt-1">
            <Citations cits={item.proposal.citations} empty="—" />
          </div>
          <button
            className="mt-2 rounded bg-ink px-3 py-1.5 text-paper"
            onClick={() =>
              send("edit", {
                gold_chunk_ids: item.proposal!.gold_chunk_ids ?? d.gold_chunk_ids ?? [],
                ...(item.proposal!.required_chunk_ids ? { required_chunk_ids: item.proposal!.required_chunk_ids } : {}),
              })
            }
          >
            اعتماد التعديل المقترح
          </button>
        </div>
      )}
      <label className="mt-3 grid gap-1 text-sm">
        <span className="text-muted">ملاحظة (اختيارية)</span>
        <input value={note} onChange={(e) => setNote(e.target.value)} className="rounded border border-line bg-surface p-2" />
      </label>
      {editing ? (
        <Editor item={item} chunks={chunks} onSave={(e) => send("edit", e)} onCancel={() => setEditing(false)} />
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="rounded bg-thread-strong px-3 py-1.5 text-white" onClick={() => send("approve")}>
            اعتماد
          </button>
          <button className="rounded border border-line px-3 py-1.5" onClick={() => setEditing(true)}>
            تعديل
          </button>
          <button className="rounded border border-madder/50 px-3 py-1.5 text-madder" onClick={() => send("remove")}>
            حذف
          </button>
          {r && (
            <button
              className="ms-auto rounded border border-line px-3 py-1.5 text-sm"
              onClick={() =>
                call(`/${item.id}`, "DELETE")
                  .then(onDone)
                  .catch((e: Error) => setErr(e.message))
              }
            >
              تراجع عن القرار
            </button>
          )}
        </div>
      )}
      {err && (
        <p role="alert" className="mt-2 text-sm text-madder">
          {err}
        </p>
      )}
    </li>
  );
}

export default function QuestionReview() {
  const [data, setData] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"pending" | "all" | "official">("pending");
  const load = useCallback(() => {
    call<Listing>("")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  const shown = (data?.items ?? []).filter((i) => (filter === "pending" ? !i.review : filter === "official" ? i.official_no != null : true));
  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <Link href="/review" className="text-sm text-insight underline">
        العودة إلى المراجعة
      </Link>
      <h1 className="mt-2 text-3xl font-semibold">مراجعة أسئلة التقييم</h1>
      <p className="mt-2 leading-relaxed text-muted">
        صاغ الوكيل الآلي هذه الأسئلة، ويعتمدها المراجِع البشري أو يعدّلها أو يحذفها. لا يدخل في التقييم إلا ما اعتُمد أو عُدِّل، ويُسجَّل اسم المراجِع وتاريخ القرار.
      </p>
      {error && (
        <p role="alert" className="mt-4 rounded border border-madder/40 p-3 text-madder">
          {error}. أدخلي رمز المراجعة في{" "}
          <Link href="/review/gold" className="underline">
            صفحة مراجعة مجموعة المرجع
          </Link>
          .
        </p>
      )}
      {data && (
        <>
          <div className="sticky top-[env(safe-area-inset-top,0px)] z-10 mt-4 flex flex-wrap items-center gap-3 border-b border-line bg-paper/95 py-3">
            <span className="text-sm">
              التقدم: {toArabicDigits(data.progress.done)} من {toArabicDigits(data.progress.total)}
            </span>
            <div className="h-2 min-w-24 flex-1 overflow-hidden rounded bg-line">
              <div className="h-full bg-thread" style={{ width: `${(100 * data.progress.done) / data.progress.total}%` }} />
            </div>
            <div className="flex gap-1 text-sm" role="tablist">
              {(
                [
                  ["pending", "بانتظار القرار"],
                  ["official", "الحالات الرسمية"],
                  ["all", "الكل"],
                ] as const
              ).map(([k, l]) => (
                <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)} className={`rounded px-3 py-1 ${filter === k ? "bg-ink text-paper" : "border border-line"}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>
          {shown.length === 0 && <p className="mt-6 text-muted">لا توجد أسئلة في هذا العرض.</p>}
          <ul className="mt-4 grid gap-4">
            {shown.map((i) => (
              <Card key={i.id + (i.review?.decided_at ?? "")} item={i} chunks={data.chunks} onDone={load} />
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
