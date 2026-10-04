"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { CopyCitation, HadithGrade, QuranCheck } from "@/components/Bits";
import { PageViewer, TYPE_COLORS, TYPE_LABELS, type PageViewerHandle } from "@/components/PageViewer";
import { ar, getJSON } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { BOOK_ID, type Block, type PageData } from "@/lib/types";

const pid = (n: number) => `${BOOK_ID}-p${String(n).padStart(3, "0")}`;

export default function SourceViewerPage() {
  return (
    <Suspense fallback={<main className="p-8">جارٍ التحميل…</main>}>
      <SourceViewer />
    </Suspense>
  );
}

function SourceViewer() {
  const t = useT();
  const { page: pageParam } = useParams<{ book: string; page: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const printed = Number(pageParam);
  const [data, setData] = useState<PageData | null>(null);
  const [error, setError] = useState("");
  const [xray, setXray] = useState(search.get("xray") === "1");
  const [selected, setSelected] = useState<string[]>(() => (search.get("hl") ?? "").split(",").filter(Boolean));
  const viewer = useRef<PageViewerHandle>(null);

  useEffect(() => {
    getJSON<PageData>(`/pages/${pid(printed)}`)
      .then(setData)
      .catch(() => setError("تعذّر تحميل الصفحة. تأكد أن رقم الصفحة بين ١٢ و٤١."));
  }, [printed]);

  useEffect(() => {
    if (data && selected.length) viewer.current?.focusBlocks(selected);
  }, [data, selected]);

  // Keyboard: arrows move between pages (RTL: left = next), Esc clears the selection.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      const rtl = document.documentElement.dir === "rtl";
      if (e.key === (rtl ? "ArrowLeft" : "ArrowRight") && data?.next) router.push(`/b/${BOOK_ID}/p/${printed + 1}`);
      if (e.key === (rtl ? "ArrowRight" : "ArrowLeft") && data?.prev) router.push(`/b/${BOOK_ID}/p/${printed - 1}`);
      if (e.key === "Escape") setSelected([]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [data, printed, router]);

  const quranBy = useMemo(() => {
    const m: Record<string, PageData["quran"]> = {};
    data?.quran.forEach((q) => (m[q.block_id] ??= []).push(q));
    return m;
  }, [data]);
  const hadithBy = useMemo(() => {
    const m: Record<string, PageData["hadith"][number]> = {};
    data?.hadith.forEach((h) => h.block_ids?.forEach((b) => (m[b] = h)));
    return m;
  }, [data]);

  if (error) return <main className="mx-auto max-w-3xl p-8 text-madder">{error}</main>;
  if (!data || data.printed !== printed)
    return <main className="mx-auto max-w-3xl p-8">جارٍ تحميل الصفحة…</main>;

  const select = (b: Block) => setSelected([b.id]);
  const notesFor = (b: Block) =>
    data.footnote_links.filter((l) => l.anchor_block_id === b.id).map((l) => data.blocks.find((x) => x.id === l.footnote_block_id));

  return (
    <main className="mx-auto grid w-full max-w-7xl flex-1 gap-5 px-4 py-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      {/* Knowledge pane (reading start: right in RTL) */}
      <section aria-label="كتل الصفحة" className="order-2 lg:order-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm text-muted">رياض الصالحين · طبعة ١٩٥٦</p>
            <h1 className="text-2xl font-semibold">صفحة {ar(data.printed)}</h1>
          </div>
          <div className="flex items-center gap-2">
            {data.prev && (
              <Link className="rounded-md border border-line px-3 py-1.5 text-sm" href={`/b/${BOOK_ID}/p/${printed - 1}`}>
                → {t("prev")}
              </Link>
            )}
            {data.next && (
              <Link className="rounded-md border border-line px-3 py-1.5 text-sm" href={`/b/${BOOK_ID}/p/${printed + 1}`}>
                {t("next")} ←
              </Link>
            )}
          </div>
        </div>
        {data.uncovered_regions.length > 0 && (
          <p className="mt-3 rounded-md border border-amber/50 bg-amber/10 p-2 text-sm text-amber-ink">
            ⚠ فحص الاكتمال وجد سطرًا مطبوعًا لم يغطّه النص المستخرج؛ الصفحة في قائمة المراجعة البشرية.
          </p>
        )}
        <ol className="mt-4 grid gap-3">
          {data.blocks
            .filter((b) => b.type !== "page_number")
            .map((b) => {
              const active = selected.includes(b.id);
              const low = b.confidence < 0.75 || b.flags.some((f) => !f.startsWith("position"));
              const editor = b.author_role === "editor";
              return (
                <li
                  key={b.id}
                  className={`rounded-lg border p-3 transition-colors ${active ? "border-thread bg-thread/10" : "border-line bg-surface"}`}
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="inline-block size-2.5 rounded-full" style={{ background: TYPE_COLORS[b.type] }} aria-hidden />
                    <span className="font-medium">{TYPE_LABELS[b.type] ?? b.type}</span>
                    <span className="text-muted">· {editor ? t("editor_label") : t("matn_label")}</span>
                    {b.footnote_marker && b.type === "footnote" && <span className="text-muted">· {b.footnote_marker}</span>}
                    <button className="ms-auto rounded border border-line px-2 py-0.5" onClick={() => select(b)}>
                      موضعها في الصفحة
                    </button>
                    <CopyCitation text={b.text} citation={data.citation} />
                  </div>
                  <p
                    className={`mt-2 text-lg ${b.type === "quran" ? "quran-text" : "source-text"} ${low ? "underline decoration-amber decoration-dotted decoration-2 underline-offset-8" : ""}`}
                    title={low ? "ثقة منخفضة أو تنبيه: راجع الصفحة الأصلية" : undefined}
                  >
                    {b.text}
                  </p>
                  {quranBy[b.id]?.map((q, i) => <div key={i} className="mt-2"><QuranCheck q={q} /></div>)}
                  {b.type === "hadith" && hadithBy[b.id] && (
                    <div className="mt-2">
                      <HadithGrade h={hadithBy[b.id]} />
                    </div>
                  )}
                  {notesFor(b).length > 0 && (
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-muted">
                        {t("footnotes")} ({ar(notesFor(b).length)})
                      </summary>
                      <ul className="mt-1 grid gap-1">
                        {notesFor(b).map((f) => f && <li key={f.id} className="source-text">{f.text}</li>)}
                      </ul>
                    </details>
                  )}
                </li>
              );
            })}
        </ol>
      </section>

      {/* Page pane */}
      <section aria-label="الصفحة الأصلية" className="order-1 lg:order-2">
        <div className="sticky top-16">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <button
              aria-pressed={xray}
              onClick={() => setXray((x) => !x)}
              className={`rounded-md px-3 py-1.5 text-sm ${xray ? "bg-insight text-white" : "border border-line"}`}
            >
              {t("xray")} {xray ? "✓" : ""}
            </button>
            <button className="rounded-md border border-line px-3 py-1.5 text-sm" onClick={() => viewer.current?.reset()}>
              الصفحة كاملة
            </button>
            {xray && (
              <ul className="flex flex-wrap gap-2 text-xs text-muted" aria-label="دليل الألوان">
                {["body", "hadith", "quran", "footnote", "editor_commentary", "heading", "poetry"].map((k) => (
                  <li key={k} className="flex items-center gap-1">
                    <span className="inline-block size-2.5 rounded-sm" style={{ background: TYPE_COLORS[k] }} />
                    {TYPE_LABELS[k]}
                  </li>
                ))}
                <li>· الخط البنفسجي: من علامة الحاشية إلى الحاشية · المتقطع: موضع من النموذج البصري</li>
              </ul>
            )}
          </div>
          <PageViewer ref={viewer} page={data} highlight={selected} xray={xray} onBlockClick={select} className="h-[min(78vh,1100px)]" />
        </div>
      </section>
    </main>
  );
}
