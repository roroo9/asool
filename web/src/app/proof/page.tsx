"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ar, getJSON } from "@/lib/api";

type Row = {
  system: string;
  role: string;
  cer_strict: number;
  cer_loose: number;
  wer_loose: number;
  footnote_f1: number;
  type_acc: number | null;
  usd_per_page: number | null;
};
type Bakeoff = { available: boolean; pages?: number[]; rows?: Row[] };
type KnownErrors = { errors: { page: number; block: string; parser_text: string; printed_text: string; kind: string; caught_by: string; owner_confirmation: string }[] };
type Summary = {
  available: boolean;
  generated_at?: string;
  metrics?: Record<string, { asool: number; baseline?: number | null; n?: number; note?: string; fmt?: string }>;
  official_cases?: { id: string; question: string; expected: string; status: string; pass: boolean; note?: string }[];
  limits?: string[];
  heldout?: {
    pages: number;
    rows: {
      system: string;
      as_output_strict: number;
      as_output_loose: number;
      normalized_strict: number;
      normalized_loose: number;
      footnotes_in_order: number | null;
      bakeoff_normalized_strict: number | null;
    }[];
  } | null;
  gold?: {
    pages: number;
    finalized: number;
    words: number;
    auto_accepted: number;
    human_decisions: number;
    typed_corrections: number;
    auto_equivalent: number;
    reviewers: string[];
    spotcheck: Record<string, { checked: number; wrong: number }>;
  };
};

const HELD_AR: Record<string, string> = {
  "Gemini 3.1 Pro + prompt v2 (Asool's parser)": "Gemini 3.1 Pro + التعليمات v2 (محلل أصول)",
  "Gemini 3.1 Pro + prompt v1": "Gemini 3.1 Pro + التعليمات v1",
  "Gemini 3.5 Flash (free tier)": "Gemini 3.5 Flash",
  "Asool final index (after fusion, splits, corrections)": "فهرس أصول النهائي (بعد الدمج والتصحيح وترتيب الحواشي)",
  "Tesseract ara (baseline)": "Tesseract (الأساس)",
};
const SPOT_AR: Record<string, string> = {
  agree: "كلمات اتفقت عليها القراءات الثلاث",
  abstain: "كلمات حُسم تشكيلها بعد امتناع قارئ",
  abstain_a: "كلمات حُسمت بعد امتناع Tesseract",
};

const NAMES: Record<string, string> = {
  "openrouter:google/gemini-3.1-pro-preview@page_parse.v2": "Gemini 3.1 Pro + v2 (أصول)",
  "openrouter:google/gemini-3.1-pro-preview": "Gemini 3.1 Pro",
  "openrouter:google/gemini-3.8-flash": "Gemini 3.8 Flash",
  "openrouter:google/gemini-3.8-flash@page_parse.v2": "Gemini 3.8 Flash + v2",
  "gemini-3.5-flash": "Gemini 3.5 Flash",
  "openrouter:openai/gpt-5.6-terra": "GPT-5.6 Terra",
  "openrouter:qwen/qwen3-vl-32b-instruct": "Qwen3-VL 32B",
  "tesseract-ara": "Tesseract (الأساس)",
  "surya-ocr-2": "Surya OCR",
  "claude-opus-5-5": "Claude Opus 5.5 (قارئ المرجع)",
  "claude-fable-5-1": "Claude Fable 5.1 (قارئ المرجع)",
};
const pct = (x: number) => `${ar((x * 100).toFixed(1))}٪`;
const fmt = (x: number, f?: string) => (f === "decimal" ? ar(x.toFixed(2)) : pct(x));

function Bars({ rows }: { rows: Row[] }) {
  const max = Math.max(...rows.map((r) => r.cer_strict));
  return (
    <figure aria-label="نسبة خطأ الحروف مع التشكيل لكل نظام (الأقل أفضل)">
      <ul className="grid gap-1.5">
        {rows.map((r) => {
          const chosen = r.system.endsWith("@page_parse.v2") && r.system.includes("3.1-pro");
          const gold = r.role.includes("not eligible") || r.role.includes("gold");
          return (
            <li key={r.system} className="grid grid-cols-[11rem_1fr_4rem] items-center gap-2 text-sm">
              <span className={chosen ? "font-semibold" : ""}>{NAMES[r.system] ?? r.system}</span>
              <span className="h-3 rounded bg-line">
                <span
                  className={`block h-3 rounded ${chosen ? "bg-thread-strong" : gold ? "bg-muted/40" : "bg-insight/60"}`}
                  style={{ width: `${(r.cer_strict / max) * 100}%` }}
                />
              </span>
              <span className="tabular-nums">{pct(r.cer_strict)}</span>
            </li>
          );
        })}
      </ul>
      <figcaption className="mt-2 text-xs text-muted">
        نسبة خطأ الحروف مع التشكيل (CER) على ٣ صفحات مراجَعة بشريًا. الأخضر: النموذج المختار. الرمادي: قارئا مجموعة المرجع (غير مؤهلين، ودرجاتهما منحازة لصالحهما).
      </figcaption>
    </figure>
  );
}

export default function ProofPage() {
  const [bake, setBake] = useState<Bakeoff | null>(null);
  const [errs, setErrs] = useState<KnownErrors | null>(null);
  const [sum, setSum] = useState<Summary | null>(null);
  useEffect(() => {
    getJSON<Bakeoff>("/eval/bakeoff").then(setBake).catch(() => setBake({ available: false }));
    getJSON<KnownErrors>("/eval/known-errors").then(setErrs).catch(() => {});
    getJSON<Summary>("/eval/summary").then(setSum).catch(() => setSum({ available: false }));
  }, []);
  const rows = (bake?.rows ?? []).slice().sort((a, b) => a.cer_strict - b.cer_strict);
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
      <h1 className="text-3xl font-semibold">البرهان</h1>
      <p className="mt-2 max-w-3xl leading-relaxed text-muted">
        كل رقم في هذه الصفحة محسوب من بيانات المشروع ويُعاد إنتاجه بأمر واحد. لا توجد أرقام مكتوبة يدويًا في الواجهة.
      </p>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">١. دقة قراءة الصفحات (اختيار النموذج)</h2>
        <p className="mt-1 text-sm text-muted">
          الصفحات {bake?.pages?.map(ar).join("، ")}: حواشٍ في عمودين وتعليق المحقق، آيات، وصفحة كثيفة. مجموعة المرجع: ثلاث قراءات مستقلة ثم مراجعة بشرية لكل موضع خلاف.
        </p>
        {!bake && <p className="mt-3">جارٍ التحميل…</p>}
        {bake && !bake.available && <p className="mt-3">النتائج غير متاحة بعد.</p>}
        {rows.length > 0 && (
          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <Bars rows={rows} />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-start">
                    <th className="py-1 text-start">النظام</th>
                    <th>CER مع التشكيل</th>
                    <th>CER بلا تشكيل</th>
                    <th>ربط الحواشي F1</th>
                    <th>$/صفحة</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.system} className="border-b border-line/60">
                      <td className="py-1">{NAMES[r.system] ?? r.system}</td>
                      <td className="text-center tabular-nums">{pct(r.cer_strict)}</td>
                      <td className="text-center tabular-nums">{pct(r.cer_loose)}</td>
                      <td className="text-center tabular-nums">{ar(r.footnote_f1.toFixed(2))}</td>
                      <td className="text-center tabular-nums">{r.usd_per_page == null ? "محلي" : ar(r.usd_per_page.toFixed(3))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {sum?.gold && (
        <section className="mt-10">
          <h2 className="text-xl font-semibold">مجموعة المرجع: المراجعة البشرية</h2>
          <p className="mt-1 text-sm text-muted">
            {ar(sum.gold.finalized)} صفحة معتمدة من {ar(sum.gold.pages)}، المراجِعة: {sum.gold.reviewers.join("، ")}. الكلمات: {ar(sum.gold.words)}؛ المقبولة تلقائيًا باتفاق القراءات: {ar(sum.gold.auto_accepted)}؛ قرارات بشرية: {ar(sum.gold.human_decisions)} (منها {ar(sum.gold.typed_corrections)} تصحيحًا كُتب يدويًا)؛ قراءات متكافئة قُبلت آليًا (فرق مسافات أو ترتيب علامات فقط): {ar(sum.gold.auto_equivalent)}.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-1 text-start">عينة التحقق العشوائية</th>
                  <th>فُحص</th>
                  <th>خطأ</th>
                  <th>نسبة الخطأ</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(sum.gold.spotcheck).map(([k, v]) => (
                  <tr key={k} className="border-b border-line/60">
                    <td className="py-1">{SPOT_AR[k] ?? k}</td>
                    <td className="text-center tabular-nums">{ar(v.checked)}</td>
                    <td className="text-center tabular-nums">{ar(v.wrong)}</td>
                    <td className="text-center tabular-nums">{pct(v.checked ? v.wrong / v.checked : 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {sum?.heldout && (
        <section className="mt-10">
          <h2 className="text-xl font-semibold">١ب. إعادة القياس على {ar(sum.heldout.pages)} صفحة محجوزة لم يُختر عليها النموذج</h2>
          <p className="mt-1 text-sm text-muted">
            نسبة خطأ الحروف (الأقل أفضل). «كما أخرجه النظام»: بترتيب النص الذي أخرجه، كما في جدول اختيار النموذج. «بعد توحيد ترتيب الحواشي»: الحواشي بترتيب أرقامها في المرجع وفي كل نظام، فيقيس دقة القراءة وحدها. Tesseract نص مسطح لا يمكن ترتيبه.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-1 text-start">النظام</th>
                  <th>كما أخرجه: مع التشكيل</th>
                  <th>كما أخرجه: بلا تشكيل</th>
                  <th>بعد التوحيد: مع التشكيل</th>
                  <th>بعد التوحيد: بلا تشكيل</th>
                  <th>الحواشي بترتيب القراءة</th>
                  <th>صفحات الاختيار الثلاث (بعد التوحيد)</th>
                </tr>
              </thead>
              <tbody>
                {sum.heldout.rows.map((r) => (
                  <tr key={r.system} className="border-b border-line/60">
                    <td className="py-1">{HELD_AR[r.system] ?? r.system}</td>
                    <td className="text-center tabular-nums">{pct(r.as_output_strict)}</td>
                    <td className="text-center tabular-nums">{pct(r.as_output_loose)}</td>
                    <td className="text-center tabular-nums">{pct(r.normalized_strict)}</td>
                    <td className="text-center tabular-nums">{pct(r.normalized_loose)}</td>
                    <td className="text-center tabular-nums">{r.footnotes_in_order == null ? "—" : pct(r.footnotes_in_order)}</td>
                    <td className="text-center tabular-nums">{r.bakeoff_normalized_strict == null ? "—" : pct(r.bakeoff_normalized_strict)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-xl font-semibold">٢. أخطاء حقيقية اكتشفها النظام بنفسه</h2>
        <p className="mt-1 text-sm text-muted">
          فحص الاكتمال يقارن نص النموذج بأسطر الصفحة المطبوعة؛ ما لا يغطيه يذهب إلى المراجعة البشرية ولا يُفهرس بصمت.
        </p>
        <ul className="mt-3 grid gap-3">
          {errs?.errors.map((e) => (
            <li key={`${e.page}${e.block}`} className="rounded-xl border border-line bg-surface p-4">
              <p className="text-sm text-muted">
                صفحة {ar(e.page)} · {e.block} · {e.caught_by}
              </p>
              <p className="mt-2">
                كتب النموذج: <span className="source-text text-madder line-through">{e.parser_text}</span>
              </p>
              <p>
                المطبوع: <span className="source-text text-thread-strong">{e.printed_text}</span>
              </p>
              <p className="mt-1 text-xs text-muted">{e.owner_confirmation}</p>
              <Link href={`/b/riyad1956/p/${e.page}?xray=1`} className="mt-1 inline-block text-sm text-insight underline">
                افتح الصفحة ↗
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">٣. الاسترجاع والإجابة والأمان، وحالات الاختبار الرسمية</h2>
        {sum?.available && sum.metrics ? (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-1 text-start">المقياس</th>
                  <th>أصول</th>
                  <th>الطريقة التقليدية</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(sum.metrics).map(([k, v]) => (
                  <tr key={k} className="border-b border-line/60">
                    <td className="py-1">
                      {k}
                      {v.n != null && <span className="text-xs text-muted"> (ن = {ar(v.n)})</span>}
                      {v.note && <span className="block text-xs text-muted">{v.note}</span>}
                    </td>
                    <td className="text-center tabular-nums">{fmt(v.asool, v.fmt)}</td>
                    <td className="text-center tabular-nums">{v.baseline == null ? "—" : fmt(v.baseline, v.fmt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-2 rounded-md border border-dashed border-line p-4 text-sm text-muted">
            تُحسب هذه المقاييس في مرحلة التقييم (Recall@5، اكتمال السياق، إمكانية التتبع، الامتناع، الإحالة، والحالات الاثنتا عشرة من الحزمة العلمية) وتظهر هنا تلقائيًا من ملف النتائج.
          </p>
        )}
        {sum?.official_cases && (
          <ul className="mt-4 grid gap-2">
            {sum.official_cases.map((c) => (
              <li key={c.id} className="rounded-lg border border-line bg-surface p-3 text-sm">
                <span className={c.pass ? "text-thread-strong" : "text-madder"}>{c.pass ? "✓" : "✗"}</span> {c.question}
                <span className="block text-muted">المتوقع: {c.expected} · الناتج: {c.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-10 grid gap-6 md:grid-cols-2">
        <div>
          <h2 className="text-xl font-semibold">المنهج</h2>
          <ul className="mt-2 list-disc space-y-1 ps-5 text-sm leading-relaxed">
            <li>الكتاب: رياض الصالحين، طبعة ١٩٥٦، الصفحات ١٢–٤١ (٣٠ صفحة).</li>
            <li>مجموعة المرجع: ١٥ صفحة، ثلاث قراءات مستقلة (Tesseract، Claude Opus، Claude Fable/Surya)، وكل موضع خلاف حسمته المراجِعة رَوان، مع عينة تحقق عشوائية.</li>
            <li>محلل أصول (Gemini) ليس من قراء مجموعة المرجع، حتى لا يُقيَّم النموذج بمرجع صنعه بنفسه.</li>
            <li>الطريقة التقليدية: نص Tesseract مقطّع إلى ٥٠٠ حرف، بالتضمين والبحث والنموذج أنفسها.</li>
          </ul>
        </div>
        <div>
          <h2 className="text-xl font-semibold">الحدود</h2>
          <ul className="mt-2 list-disc space-y-1 ps-5 text-sm leading-relaxed">
            <li>مدونة صغيرة (٣٠ صفحة) وكتاب واحد في نوع واحد.</li>
            <li>اختير النموذج وحُسّنت التعليمات على ٣ صفحات؛ وأُعيد القياس على ١٢ صفحة محجوزة: تحسّن دقة القراءة ثبت، أما ترتيب الحواشي ذات العمودين فلم يثبت، فصار يُرتَّب آليًا بأرقام الحواشي.</li>
            <li>درجات Claude منحازة لأنه كان القراءة المحورية في مجموعة المرجع.</li>
            <li>فحص الاكتمال لا يكشف نقصًا أقصر من سطر مطبوع.</li>
          </ul>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">أعد التقييم بنفسك</h2>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-ink p-4 text-sm text-paper" dir="ltr">
{`git clone https://github.com/roroo9/asool && cd asool
uv sync && ./scripts/fetch_references.sh
uv run python -m eval.bakeoff        # page reading (needs the book PDF + keys)
uv run python -m eval.run_eval retrieval      # Asool vs baseline (free)
uv run python -m eval.run_eval answers --runs 3  # ~$0.03 per question per run
uv run python -m eval.heldout_eval           # 12 held-out gold pages
uv run python -m eval.report                 # -> summary.json -> this page
uv run pytest                        # unit tests`}
        </pre>
      </section>
    </main>
  );
}
