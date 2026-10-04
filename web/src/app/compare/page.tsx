"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { TYPE_COLORS, TYPE_LABELS } from "@/components/PageViewer";
import { PassageCard } from "@/components/PassageCard";
import { ar, getJSON, imageUrl } from "@/lib/api";
import type { PageData, Passage } from "@/lib/types";

type Naive = { lines: { text: string; bbox: number[] }[]; engine: string };
const PAGES = Array.from({ length: 30 }, (_, i) => i + 12);
const pid = (n: number) => `riyad1956-p${String(n).padStart(3, "0")}`;

function Slider({ page, naive }: { page: PageData; naive: Naive }) {
  const [pos, setPos] = useState(50); // % from the left edge
  const box = useRef<HTMLDivElement>(null);
  const drag = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (r) setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)));
  };
  const W = page.width;
  const H = page.height;
  return (
    <div>
      <div
        ref={box}
        className="relative w-full touch-none select-none overflow-hidden rounded-lg border border-line bg-white"
        style={{ aspectRatio: `${W} / ${H}` }}
        onPointerMove={(e) => e.buttons === 1 && drag(e.clientX)}
        onPointerDown={(e) => drag(e.clientX)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imageUrl(page.id)} alt={`صفحة ${ar(page.printed)}`} className="absolute inset-0 h-full w-full" draggable={false} />
        {/* Left of the handle: naive extraction (OCR lines, no structure) */}
        <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} aria-hidden>
          <rect width={W} height={H} fill="#fff" fillOpacity={0.35} />
          {naive.lines.map((l, i) => (
            <rect key={i} x={l.bbox[0]} y={l.bbox[1]} width={l.bbox[2] - l.bbox[0]} height={l.bbox[3] - l.bbox[1]} fill="#9aa0b4" fillOpacity={0.28} stroke="#6b7186" strokeWidth={3} />
          ))}
        </svg>
        {/* Right of the handle: Asool blocks by type + footnote links */}
        <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full" style={{ clipPath: `inset(0 0 0 ${pos}%)` }} aria-hidden>
          {page.blocks.map((b) =>
            (b.rects?.length ? b.rects : b.bbox ? [b.bbox] : []).map((r, k) => (
              <rect key={`${b.id}${k}`} x={r[0]} y={r[1]} width={r[2] - r[0]} height={r[3] - r[1]} fill={TYPE_COLORS[b.type]} fillOpacity={0.14} stroke={TYPE_COLORS[b.type]} strokeWidth={5} />
            )),
          )}
          {page.footnote_links.map((ln, i) => {
            const a = page.blocks.find((b) => b.id === ln.anchor_block_id)?.bbox;
            const f = page.blocks.find((b) => b.id === ln.footnote_block_id)?.bbox;
            if (!a || !f) return null;
            const p = [(a[0] + a[2]) / 2, (a[1] + a[3]) / 2];
            const q = [(f[0] + f[2]) / 2, f[1]];
            return <path key={i} d={`M ${p[0]} ${p[1]} Q ${(p[0] + q[0]) / 2 + 140} ${(p[1] + q[1]) / 2} ${q[0]} ${q[1]}`} fill="none" stroke="#6c5ce7" strokeWidth={5} strokeOpacity={0.7} />;
          })}
        </svg>
        <div className="absolute inset-y-0 w-0.5 bg-ink" style={{ left: `${pos}%` }}>
          <button
            role="slider"
            aria-label="شريط المقارنة: يسار = الاستخراج التقليدي، يمين = أصول"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(pos)}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setPos((p) => Math.max(0, p - 5));
              if (e.key === "ArrowRight") setPos((p) => Math.min(100, p + 5));
            }}
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-paper px-2 py-1 text-xs shadow"
          >
            ⇆
          </button>
        </div>
        <span className="absolute left-2 top-2 rounded bg-ink/80 px-2 py-0.5 text-xs text-paper">استخراج تقليدي</span>
        <span className="absolute right-2 top-2 rounded bg-thread-strong px-2 py-0.5 text-xs text-white">أصول</span>
      </div>
    </div>
  );
}

function PageMode() {
  const [n, setN] = useState(41);
  const [page, setPage] = useState<PageData | null>(null);
  const [naive, setNaive] = useState<Naive | null>(null);
  useEffect(() => {
    Promise.all([getJSON<PageData>(`/pages/${pid(n)}`), getJSON<Naive>(`/pages/${pid(n)}/naive`)]).then(([p, nv]) => {
      setPage(p);
      setNaive(nv);
    });
  }, [n]);
  const ready = page && naive && page.printed === n;
  const fnCount = page?.blocks.filter((b) => b.type === "footnote").length ?? 0;
  return (
    <div>
      <label className="flex items-center gap-2 text-sm">
        الصفحة
        <select value={n} onChange={(e) => setN(Number(e.target.value))} className="rounded border border-line bg-surface px-2 py-1">
          {PAGES.map((p) => (
            <option key={p} value={p}>
              {ar(p)}
              {p === 41 ? " (حواشٍ وتعليق المحقق)" : p === 30 ? " (آيات)" : ""}
            </option>
          ))}
        </select>
      </label>
      {!ready ? (
        <p className="mt-6">جارٍ التحميل…</p>
      ) : (
        <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Slider page={page} naive={naive} />
          <div className="grid gap-4 sm:grid-cols-2">
            <section className="rounded-lg border border-line bg-surface p-3">
              <h2 className="font-semibold">الاستخراج التقليدي</h2>
              <p className="text-xs text-muted">{naive.engine}: نص مسطح بترتيب الأسطر، الحواشي مختلطة بالمتن، بلا أنواع ولا روابط</p>
              <p className="source-text mt-2 max-h-[70vh] overflow-auto whitespace-pre-line text-sm">{naive.lines.map((l) => l.text).join("\n")}</p>
            </section>
            <section className="rounded-lg border border-thread/50 bg-surface p-3">
              <h2 className="font-semibold">أصول</h2>
              <p className="text-xs text-muted">
                {ar(page.blocks.length)} كتلة مصنفة · {ar(fnCount)} حاشية مربوطة بعلاماتها · {ar(page.quran.length)} آية متحقق منها
              </p>
              <ol className="mt-2 grid max-h-[70vh] gap-2 overflow-auto">
                {page.blocks
                  .filter((b) => b.type !== "page_number")
                  .map((b) => (
                    <li key={b.id} className="rounded border-s-4 bg-background/50 p-2" style={{ borderColor: TYPE_COLORS[b.type] }}>
                      <span className="text-xs font-medium" style={{ color: TYPE_COLORS[b.type] }}>
                        {TYPE_LABELS[b.type]}
                        {b.author_role === "editor" ? " · المحقق" : ""}
                      </span>
                      <p className={`text-sm ${b.type === "quran" ? "quran-text" : "source-text"}`}>{b.text}</p>
                    </li>
                  ))}
              </ol>
              <Link href={`/b/riyad1956/p/${n}?xray=1`} className="mt-2 inline-block text-sm text-insight underline">
                افتح الصفحة في عارض المصدر ↗
              </Link>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}

type SearchRes = { results: Passage[] };

function QueryMode() {
  const [q, setQ] = useState("ما شروط التوبة؟");
  const [run, setRun] = useState("ما شروط التوبة؟");
  const [res, setRes] = useState<{ base: Passage[]; asool: Passage[]; q: string } | null>(null);
  useEffect(() => {
    const enc = encodeURIComponent(run);
    Promise.all([getJSON<SearchRes>(`/search?k=3&mode=baseline&q=${enc}`), getJSON<SearchRes>(`/search?k=3&q=${enc}`)]).then(([b, a]) =>
      setRes({ base: b.results, asool: a.results, q: run }),
    );
  }, [run]);
  const cutMid = (t: string) => !/[.:؟!»)]\s*$/.test(t.trim());
  return (
    <div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setRun(q);
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2" aria-label="سؤال المقارنة" />
        <button className="rounded-lg bg-ink px-4 text-paper">قارن</button>
      </form>
      <p className="mt-2 text-xs text-muted">الطريقتان تستخدمان نفس التضمين ونفس البحث الهجين؛ الفرق الوحيد هو تجهيز البيانات.</p>
      {res && res.q === run && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section>
            <h2 className="mb-2 font-semibold">الطريقة التقليدية (مقاطع ثابتة ٥٠٠ حرف)</h2>
            <div className="grid gap-3">
              {res.base.map((p, i) => (
                <article key={p.id} className="rounded-xl border border-line bg-surface p-4">
                  <p className="text-xs text-muted">
                    {ar(i + 1)} · ص {ar(p.pages[0]?.printed ?? "")} تقريبًا · بلا حواشٍ · بلا موضع في الصفحة
                    {cutMid(p.text) ? " · ⚠ مقطوع في وسط الجملة" : ""}
                  </p>
                  <p className="source-text mt-1 text-sm">{p.text}</p>
                </article>
              ))}
            </div>
          </section>
          <section>
            <h2 className="mb-2 font-semibold">أصول (وحدات كاملة مع حواشيها)</h2>
            <div className="grid gap-3">
              {res.asool.map((p, i) => (
                <PassageCard key={p.id} p={p} tag={`${ar(i + 1)}`} />
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default function ComparePage() {
  const [mode, setMode] = useState<"page" | "query">("page");
  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
      <h1 className="text-2xl font-semibold">المقارنة: الطريقة التقليدية مقابل أصول</h1>
      <p className="mt-1 text-muted">نفس الصفحة ونفس السؤال؛ اسحب الشريط لترى الفرق.</p>
      <div className="mt-4 flex gap-2" role="tablist">
        {(
          [
            ["page", "صفحة"],
            ["query", "سؤال"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)} className={`rounded-md px-4 py-1.5 ${mode === k ? "bg-ink text-paper" : "border border-line"}`}>
            {label}
          </button>
        ))}
      </div>
      <div className="mt-4">{mode === "page" ? <PageMode /> : <QueryMode />}</div>
    </main>
  );
}
