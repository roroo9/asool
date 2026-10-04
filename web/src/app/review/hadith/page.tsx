"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getReviewer, getToken, toArabicDigits } from "@/lib/review";

type HadeethEnc = { id: string; hadeeth: string; attribution: string; grade: string; url: string };
type Check = {
  auto: boolean;
  narrator_book: string | null;
  narrator_hadeethenc: string | null;
  narrator_match: boolean | null;
  wording_score: number;
};
type DorarEntry = {
  grading: string;
  muhaddith: string;
  source: string;
  number: string;
  url: string;
  narrator: string;
  narrator_warning: string | null;
};
type HadithRow = {
  id: string;
  wording: string;
  narrator: string | null;
  takhrij_text: string | null;
  grading_status: "in_sahihayn" | "hadeethenc" | "hadeethenc_pending" | "dorar_manual" | "unverified";
  status_ar: string;
  grading: string | null;
  grading_source: string | null;
  grading_source_url: string | null;
  graded_by: string | null;
  dorar_search_url: string;
  hadeethenc: HadeethEnc[];
  hadeethenc_check: Check | null;
  dorar_entry: DorarEntry | null;
  page_ids: string[];
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
    throw new Error(res.status === 401 ? "رمز المراجعة غير صحيح" : String(msg));
  }
  return res.json() as Promise<T>;
}

const pageNo = (pid: string) => toArabicDigits(Number(pid.split("-p")[1]));
const reviewer = () => getReviewer() || "rawan";

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
      <h1 className="mt-2 text-3xl font-semibold">أحكام الأحاديث</h1>
      <div className="mt-3 max-w-2xl space-y-2 leading-relaxed opacity-85">
        <p>
          ما خرّجه الإمام النووي من الصحيحين يُعرض «في الصحيحين» تلقائيًا. وما سواه يُطابَق مع
          موسوعة الأحاديث النبوية (HadeethEnc)؛ فإن اتفق الراوي ونص الحديث أُخذ حكمها تلقائيًا، وإن
          لم يتأكد ذلك طُلب تأكيدك. وما لم يوجد فيها يُدخل حكمه يدويًا من الدرر السنية.
        </p>
        <p>لا يُولَّد أي حكم آليًا، وما لم يثبت له حكم يظهر للمستخدم: «الحكم غير متحقق في البيانات».</p>
      </div>
      {error && (
        <p role="alert" className="mt-4 text-madder">
          {error}
        </p>
      )}
      <ol className="mt-6 grid gap-5">
        {rows?.map((r, i) => (
          <HadithCard key={r.id} n={i + 1} row={r} onSaved={load} />
        ))}
      </ol>
    </main>
  );
}

function Badge({ row }: { row: HadithRow }) {
  const ok = ["in_sahihayn", "hadeethenc", "dorar_manual"].includes(row.grading_status);
  return (
    <span
      className={`rounded px-2 py-0.5 text-sm ${ok ? "bg-thread/20" : "bg-amber/25"}`}
    >
      {ok ? "✓ " : "⚠ "}
      {row.status_ar}
    </span>
  );
}

function HadithCard({ n, row, onSaved }: { n: number; row: HadithRow; onSaved: () => void }) {
  const [msg, setMsg] = useState("");
  const he = row.hadeethenc[0];
  const chk = row.hadeethenc_check;
  const needsDorar = row.grading_status === "unverified" || row.grading_status === "dorar_manual";
  return (
    <li className="rounded-lg border border-ink/15 bg-paper p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>
          الحديث {toArabicDigits(n)} · صفحة {row.page_ids.map(pageNo).join("، ")}
          {row.narrator && <> · الراوي في الكتاب: {row.narrator}</>}
        </span>
        <Badge row={row} />
      </div>
      <p className="mt-3 font-source text-xl leading-loose">{row.wording}</p>

      <dl className="mt-3 grid gap-1 text-sm">
        <div>
          <dt className="inline font-medium">تخريج المصنف كما طُبع: </dt>
          <dd className="inline">{row.takhrij_text ?? "لا يوجد في صفحات المدونة (قد يكون في الصفحة التالية)"}</dd>
        </div>
        <div>
          <dt className="inline font-medium">الحكم المعروض: </dt>
          <dd className="inline">
            {row.grading ?? "الحكم غير متحقق في البيانات"}
            {row.grading_source && <> — {row.grading_source}</>}
            {row.grading_source_url && (
              <>
                {" "}
                <a className="text-insight underline" href={row.grading_source_url} target="_blank" rel="noreferrer">
                  المصدر ↗
                </a>
              </>
            )}
          </dd>
        </div>
      </dl>

      {he && (
        <section className="mt-4 rounded border border-ink/10 p-3 text-sm">
          <h2 className="font-medium">موسوعة الأحاديث النبوية (HadeethEnc)</h2>
          <p className="mt-1 line-clamp-4 font-source text-base leading-loose">{he.hadeeth}</p>
          <p className="mt-1">
            التخريج: {he.attribution} · الدرجة: <strong>{he.grade}</strong> ·{" "}
            <a className="text-insight underline" href={he.url} target="_blank" rel="noreferrer">
              عرض في الموسوعة ↗
            </a>
          </p>
          {chk && (
            <p className="mt-1 opacity-80">
              فحص المطابقة: الراوي{" "}
              {chk.narrator_match === true ? "متطابق ✓" : chk.narrator_match === false ? "مختلف ✗" : "لم يمكن مقارنته"}{" "}
              ({chk.narrator_hadeethenc ?? "غير ظاهر في نص الموسوعة"}) · تطابق النص{" "}
              {toArabicDigits(Math.round(chk.wording_score))}٪
            </p>
          )}
          {row.grading_status === "hadeethenc_pending" && (
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="w-full font-medium">هل هذا هو الحديث نفسه الذي في الكتاب؟</span>
              <button
                className="rounded bg-thread px-4 py-2 text-ink"
                onClick={async () => {
                  await call(`/${row.id}/hadeethenc`, "POST", { accept: true, reviewer: reviewer() });
                  onSaved();
                }}
              >
                نعم، هو نفسه
              </button>
              <button
                className="rounded border border-madder px-4 py-2 text-madder"
                onClick={async () => {
                  await call(`/${row.id}/hadeethenc`, "POST", { accept: false, reviewer: reviewer() });
                  onSaved();
                }}
              >
                ليس هو
              </button>
            </div>
          )}
        </section>
      )}

      {needsDorar && <DorarForm row={row} onSaved={onSaved} setMsg={setMsg} />}
      {msg && (
        <p role="status" className="mt-2 text-sm">
          {msg}
        </p>
      )}
    </li>
  );
}

function DorarForm({
  row,
  onSaved,
  setMsg,
}: {
  row: HadithRow;
  onSaved: () => void;
  setMsg: (m: string) => void;
}) {
  const e = row.dorar_entry;
  const [f, setF] = useState({
    grading: e?.grading ?? "",
    muhaddith: e?.muhaddith ?? "",
    source: e?.source ?? "",
    number: e?.number ?? "",
    url: e?.url ?? "",
    narrator: e?.narrator ?? "",
  });
  const field = (k: keyof typeof f, label: string, ltr = false, required = true) => (
    <label className="grid gap-1 text-sm">
      {label}
      <input
        className="rounded border border-ink/25 bg-background px-3 py-2"
        value={f[k]}
        onChange={(ev) => setF({ ...f, [k]: ev.target.value })}
        dir={ltr ? "ltr" : undefined}
        required={required}
      />
    </label>
  );
  return (
    <section className="mt-4 rounded border border-insight/30 p-3">
      <h2 className="font-medium">إدخال الحكم من الدرر السنية</h2>
      <a
        href={row.dorar_search_url}
        target="_blank"
        rel="noreferrer"
        className="mt-2 inline-block rounded bg-insight px-4 py-2 text-white"
      >
        ابحث عنه في الدرر السنية ↗
      </a>
      <p className="mt-2 text-xs opacity-75">
        تنبيه: لا تعتمد أول نتيجة. تأكد أن الراوي ونص الحديث يطابقان ما في الكتاب.
      </p>
      {e?.narrator_warning && <p className="mt-2 text-sm text-madder">⚠ {e.narrator_warning}</p>}
      <form
        className="mt-3 grid gap-3 sm:grid-cols-2"
        onSubmit={async (ev) => {
          ev.preventDefault();
          try {
            const r = await call<{ warning: string | null }>(`/${row.id}/dorar`, "POST", {
              ...f,
              reviewer: reviewer(),
            });
            setMsg(r.warning ? `حُفظ، مع تنبيه: ${r.warning}` : "حُفظ الحكم.");
            onSaved();
          } catch (err) {
            setMsg((err as Error).message);
          }
        }}
      >
        {field("grading", "خلاصة حكم المحدث (مثال: حسن)")}
        {field("muhaddith", "المحدث (مثال: الترمذي)")}
        {field("source", "المصدر (مثال: سنن الترمذي)")}
        {field("number", "الصفحة أو الرقم")}
        {field("narrator", "الراوي كما في الدرر (للتحقق)", false, false)}
        {field("url", "رابط الحديث في الدرر السنية", true)}
        <div className="flex items-center gap-3 sm:col-span-2">
          <button className="rounded bg-ink px-4 py-2 text-paper" type="submit">
            حفظ الحكم
          </button>
          {row.grading_status === "dorar_manual" && (
            <button
              type="button"
              className="rounded border border-madder px-3 py-2 text-madder"
              onClick={async () => {
                await call(`/${row.id}`, "DELETE");
                onSaved();
              }}
            >
              حذف الحكم
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
