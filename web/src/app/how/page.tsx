"use client";

import { useEffect, useState } from "react";
import { TYPE_COLORS, TYPE_LABELS } from "@/components/PageViewer";
import { ar, getJSON, imageUrl } from "@/lib/api";
import type { PageData } from "@/lib/types";

type Naive = { lines: { text: string; bbox: number[] }[] };
const PID = "riyad1956-p041";

const STEPS = [
  { t: "صورة الصفحة", d: "صفحة ٤١ من طبعة ١٩٥٦ كما صُوّرت: متن، حديث، حواشٍ في عمودين، بيت شعر، وتعليق المحقق." },
  { t: "مسار الهندسة: أسطر OCR", d: "Tesseract يحدد مواضع الأسطر والكلمات بدقة، لكنه يقرأ النص العربي بأخطاء كثيرة." },
  { t: "مسار الفهم: كتل مصنفة", d: "نموذج بصري لغوي يقرأ الصفحة ويصنف كل كتلة: متن، حديث، حاشية، شعر، تعليق المحقق." },
  { t: "الدمج والروابط", d: "تُطابق الكتل مع أسطر OCR لتحديد مواضعها، وتُربط كل علامة حاشية بحاشيتها." },
  { t: "التحقق", d: "الآيات تُطابق مع مصحف مجمع الملك فهد، والأحاديث تُربط بتخريج المصنف وحكمها، والصفحة تُفحص للاكتمال." },
  { t: "وحدات البحث", d: "وحدات كاملة (حديث مع رواته وتخريجه وحواشيه) بدل مقاطع مقطوعة، وتعليق المحقق في وحدة مستقلة." },
];

export default function How() {
  const [page, setPage] = useState<PageData | null>(null);
  const [naive, setNaive] = useState<Naive | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  useEffect(() => {
    getJSON<PageData>(`/pages/${PID}`).then(setPage);
    getJSON<Naive>(`/pages/${PID}/naive`).then(setNaive);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) setPlaying(false);
  }, []);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 3200);
    return () => clearInterval(id);
  }, [playing]);

  const W = page?.width ?? 2146;
  const H = page?.height ?? 3025;
  const blocks = page?.blocks ?? [];
  return (
    <main className="mx-auto grid w-full max-w-6xl flex-1 gap-6 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section>
        <h1 className="text-3xl font-semibold">كيف يعمل أصول</h1>
        <p className="mt-2 text-muted">إعادة تشغيل لرحلة صفحة حقيقية عبر المراحل، من بيانات المشروع الفعلية.</p>
        <ol className="mt-6 grid gap-2">
          {STEPS.map((s, i) => (
            <li key={s.t}>
              <button
                onClick={() => {
                  setStep(i);
                  setPlaying(false);
                }}
                aria-current={step === i ? "step" : undefined}
                className={`w-full rounded-lg border p-3 text-start ${step === i ? "border-thread bg-thread/10" : "border-line"}`}
              >
                <span className="font-medium">
                  {ar(i + 1)}. {s.t}
                </span>
                {step === i && <span className="mt-1 block text-sm text-muted">{s.d}</span>}
              </button>
            </li>
          ))}
        </ol>
        <button onClick={() => setPlaying((p) => !p)} className="mt-3 rounded border border-line px-3 py-1.5 text-sm">
          {playing ? "إيقاف التشغيل التلقائي" : "تشغيل"}
        </button>
        {step >= 4 && page && (
          <div className="mt-4 rounded-lg border border-line bg-surface p-3 text-sm">
            <p>
              {ar(page.footnote_links.length)} رابط حاشية بالعلامة المطابقة · {ar(page.hadith.length)} حديث مع تخريجه وحكمه · تغطية الأسطر{" "}
              {ar(Math.round(page.coverage * 100))}٪
            </p>
            {page.hadith.map((h) => (
              <p key={h.id} className="mt-1 text-muted">
                «{h.takhrij_printed ?? "تخريج في صفحة تالية"}» ← {h.grading}
              </p>
            ))}
          </div>
        )}
      </section>
      <section aria-label="الصفحة" className="relative w-full overflow-hidden rounded-lg border border-line bg-white" style={{ aspectRatio: `${W} / ${H}` }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imageUrl(PID)} alt="صفحة ٤١ من رياض الصالحين، طبعة ١٩٥٦" className="absolute inset-0 h-full w-full" />
        <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full" aria-hidden>
          {step === 1 &&
            naive?.lines.map((l, i) => (
              <rect key={i} x={l.bbox[0]} y={l.bbox[1]} width={l.bbox[2] - l.bbox[0]} height={l.bbox[3] - l.bbox[1]} fill="#6b7186" fillOpacity={0.22} stroke="#6b7186" strokeWidth={3} />
            ))}
          {step >= 2 &&
            step <= 4 &&
            blocks.map((b) =>
              (b.rects?.length ? b.rects : b.bbox ? [b.bbox] : []).map((r, k) => (
                <rect key={`${b.id}${k}`} x={r[0]} y={r[1]} width={r[2] - r[0]} height={r[3] - r[1]} fill={TYPE_COLORS[b.type]} fillOpacity={0.15} stroke={TYPE_COLORS[b.type]} strokeWidth={5} />
              )),
            )}
          {step >= 3 &&
            step <= 4 &&
            page?.footnote_links.map((ln, i) => {
              const a = blocks.find((b) => b.id === ln.anchor_block_id)?.bbox;
              const f = blocks.find((b) => b.id === ln.footnote_block_id)?.bbox;
              if (!a || !f) return null;
              const p = [(a[0] + a[2]) / 2, (a[1] + a[3]) / 2];
              const q = [(f[0] + f[2]) / 2, f[1]];
              return <path key={i} d={`M ${p[0]} ${p[1]} Q ${(p[0] + q[0]) / 2 + 140} ${(p[1] + q[1]) / 2} ${q[0]} ${q[1]}`} fill="none" stroke="#6c5ce7" strokeWidth={6} />;
            })}
          {step === 5 &&
            (["matn", "editor"] as const).map((role) => {
              const bs = blocks.filter((b) =>
                role === "editor" ? b.type === "editor_commentary" : b.author_role === "matn" && b.bbox,
              );
              const rs = bs.map((b) => b.bbox!).filter(Boolean);
              if (!rs.length) return null;
              const r = [Math.min(...rs.map((x) => x[0])), Math.min(...rs.map((x) => x[1])), Math.max(...rs.map((x) => x[2])), Math.max(...rs.map((x) => x[3]))];
              const c = role === "editor" ? "#8b5a2b" : "#0f8f78";
              return (
                <rect key={role} x={r[0] - 10} y={r[1] - 10} width={r[2] - r[0] + 20} height={r[3] - r[1] + 20} fill={c} fillOpacity={0.12} stroke={c} strokeWidth={6} strokeDasharray={role === "editor" ? "20 10" : undefined} />
              );
            })}
        </svg>
        {step >= 2 && step <= 3 && (
          <ul className="absolute bottom-2 left-2 flex flex-wrap gap-1 rounded bg-paper/90 p-1 text-[11px]">
            {["body", "hadith", "footnote", "editor_commentary", "poetry"].map((k) => (
              <li key={k} className="flex items-center gap-1 px-1">
                <span className="inline-block size-2 rounded-sm" style={{ background: TYPE_COLORS[k] }} />
                {TYPE_LABELS[k]}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
