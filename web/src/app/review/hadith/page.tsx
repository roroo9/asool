"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getReviewer, getToken, toArabicDigits } from "@/lib/review";

type HadeethEnc = { id: string; hadeeth: string; attribution: string; grade: string; url: string };
type HadithRow = {
  id: string;
  wording: string;
  takhrij_text: string | null;
  takhrij_kind: string;
  grading_status: "in_sahihayn" | "verified" | "unverified";
  grading: string | null;
  grading_source_url: string | null;
  graded_by: string | null;
  dorar_search_url: string;
  hadeethenc: HadeethEnc[];
  page_ids: string[];
  display_status: string;
};

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`/api/review/hadith${path}`, {
    method,
    headers: { "content-type": "application/json", "x-review-token": getToken() },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const t = await res.text();
    let msg = t;
    try {
      msg = JSON.parse(t).detail ?? t;
    } catch {
      /* plain text */
    }
    throw new Error(res.status === 401 ? "رمز المراجعة غير صحيح" : msg);
  }
  return res.json() as Promise<T>;
}

const pageNo = (pid: string) => toArabicDigits(Number(pid.split("-p")[1]));

export default function HadithReview() {
  const [rows, setRows] = useState<HadithRow[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    call<HadithRow[]>("")
      .then(setRows)
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-10">
      <Link href="/review/gold" className="text-sm text-insight underline">
        مراجعة مجموعة المرجع
      </Link>
      <h1 className="mt-2 text-3xl font-semibold">أحكام الأحاديث من الدرر السنية</h1>
      <p className="mt-3 max-w-2xl leading-relaxed opacity-80">
        هذه الأحاديث خرّجها الإمام النووي من غير الصحيحين، فتحتاج حكمًا موثقًا. افتح رابط البحث في
        الدرر السنية، ثم الصق نص الحكم ورابط الصفحة. لا يُولَّد أي حكم آليًا، وما لم يُدخل له حكم
        يظهر للمستخدم: «الحكم غير متحقق في البيانات».
      </p>
      {error && (
        <p role="alert" className="mt-4 text-madder">
          {error}
        </p>
      )}
      {rows && rows.length === 0 && (
        <p className="mt-6">لا توجد أحاديث تحتاج حكمًا في المدونة الحالية.</p>
      )}
      <ol className="mt-6 grid gap-5">
        {rows?.map((r, i) => (
          <HadithCard key={r.id} n={i + 1} row={r} onSaved={load} />
        ))}
      </ol>
    </main>
  );
}

function HadithCard({ n, row, onSaved }: { n: number; row: HadithRow; onSaved: () => void }) {
  const [grading, setGrading] = useState(row.grading ?? "");
  const [url, setUrl] = useState(row.grading_source_url ?? "");
  const [msg, setMsg] = useState("");
  const verified = row.grading_status === "verified";
  return (
    <li className="rounded-lg border border-ink/15 bg-paper p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>
          الحديث {toArabicDigits(n)} · صفحة {row.page_ids.map(pageNo).join("، ")}
        </span>
        <span
          className={
            verified ? "rounded bg-thread/20 px-2 py-0.5" : "rounded bg-amber/20 px-2 py-0.5"
          }
        >
          {verified ? "✓ حكم موثق" : "⚠ الحكم غير متحقق في البيانات"}
        </span>
      </div>
      <p className="mt-3 font-source text-xl leading-loose">«{row.wording}»</p>
      <p className="mt-2 text-sm">
        تخريج المصنف كما طُبع: <strong>{row.takhrij_text ?? "لم يُعثر على تخريج"}</strong>
      </p>

      <a
        href={row.dorar_search_url}
        target="_blank"
        rel="noreferrer"
        className="mt-4 inline-block rounded bg-insight px-4 py-2 text-white"
      >
        ابحث عنه في الدرر السنية ↗
      </a>

      <form
        className="mt-4 grid gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setMsg("");
          try {
            await call(`/${row.id}`, "POST", { grading, url, reviewer: getReviewer() || "rawan" });
            setMsg("حُفظ الحكم.");
            onSaved();
          } catch (err) {
            setMsg((err as Error).message);
          }
        }}
      >
        <label className="grid gap-1 text-sm">
          الحكم كما في الدرر السنية (مثال: «حسن صحيح»، مع اسم المحدّث إن وُجد)
          <input
            className="rounded border border-ink/25 bg-background px-3 py-2"
            value={grading}
            onChange={(e) => setGrading(e.target.value)}
            required
          />
        </label>
        <label className="grid gap-1 text-sm">
          رابط النتيجة في الدرر السنية
          <input
            className="rounded border border-ink/25 bg-background px-3 py-2"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            dir="ltr"
            placeholder="https://dorar.net/hadith/sharh/..."
            required
          />
        </label>
        <div className="flex items-center gap-3">
          <button className="rounded bg-ink px-4 py-2 text-paper" type="submit">
            حفظ الحكم
          </button>
          {verified && (
            <button
              type="button"
              className="rounded border border-madder px-3 py-2 text-madder"
              onClick={async () => {
                await call(`/${row.id}`, "DELETE");
                setGrading("");
                setUrl("");
                onSaved();
              }}
            >
              حذف الحكم
            </button>
          )}
          {msg && <span role="status">{msg}</span>}
        </div>
      </form>

      <section className="mt-5 rounded border border-ink/10 p-3 text-sm">
        <h2 className="font-medium">مرجع ثانٍ: موسوعة الأحاديث النبوية (HadeethEnc)</h2>
        {row.hadeethenc.length === 0 ? (
          <p className="mt-1 opacity-70">لم يُعثر على حديث مطابق في الموسوعة.</p>
        ) : (
          row.hadeethenc.map((h) => (
            <div key={h.id} className="mt-2">
              <p className="line-clamp-3 font-source text-base leading-loose">{h.hadeeth}</p>
              <p className="mt-1">
                التخريج: {h.attribution} · الدرجة: <strong>{h.grade}</strong> ·{" "}
                <a className="text-insight underline" href={h.url} target="_blank" rel="noreferrer">
                  عرض في الموسوعة ↗
                </a>
              </p>
            </div>
          ))
        )}
      </section>
    </li>
  );
}
