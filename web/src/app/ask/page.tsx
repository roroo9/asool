"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { HadithBadge, LevelBadge, VerseChip } from "@/components/Bits";
import { PageViewer, type PageViewerHandle } from "@/components/PageViewer";
import { PassageCard } from "@/components/PassageCard";
import { SearchBox } from "@/components/SearchBox";
import { SourceThread } from "@/components/SourceThread";
import { ar, getJSON, postJSON } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { blocksForQuote, norm } from "@/lib/norm";

/** Main-text blocks plus the footnotes attached to a passage (quotes may come from either). */
const allBlocks = (p: Passage) => [...(p.blocks ?? []), ...(p.footnotes ?? [])];
import type { AnswerRes, PageData, Passage, SourcePoint } from "@/lib/types";

export default function AskPage() {
  return (
    <Suspense fallback={<main className="p-8">…</main>}>
      <Ask />
    </Suspense>
  );
}

const pageCache: Record<string, PageData> = {};
async function loadPage(id: string) {
  if (!pageCache[id]) pageCache[id] = await getJSON<PageData>(`/pages/${id}`);
  return pageCache[id];
}

function StagedLoader() {
  const t = useT();
  const stages = [t("stage_search"), t("stage_verify"), t("stage_compose")];
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((x) => Math.min(x + 1, stages.length - 1)), 2600);
    return () => clearInterval(id);
  }, [stages.length]);
  return (
    <ol className="grid gap-2" aria-live="polite">
      {stages.map((s, k) => (
        <li key={s} className={`flex items-center gap-2 ${k <= i ? "" : "opacity-40"}`}>
          <span className={`inline-block size-2.5 rounded-full ${k < i ? "bg-thread" : k === i ? "animate-pulse bg-insight" : "bg-line"}`} />
          {s}
          {k < i ? " ✓" : k === i ? "…" : ""}
        </li>
      ))}
    </ol>
  );
}

function Ask() {
  const t = useT();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const demoThread = params.get("thread") === "1";
  const firstPoint = useRef<HTMLButtonElement>(null);
  const [res, setRes] = useState<{ q: string; data: AnswerRes } | null>(null);
  const [err, setErr] = useState<{ q: string; msg: string } | null>(null);
  const [page, setPage] = useState<PageData | null>(null);
  const [hl, setHl] = useState<string[]>([]);
  const [threadFrom, setThreadFrom] = useState<HTMLElement | null>(null);
  const [sheet, setSheet] = useState(false);
  const viewer = useRef<PageViewerHandle>(null);
  const data = res?.q === q ? res.data : null;

  useEffect(() => {
    if (!q) return;
    let alive = true;
    postJSON<AnswerRes>("/answer", { question: q })
      .then((d) => alive && setRes({ q, data: d }))
      .catch(() => alive && setErr({ q, msg: "تعذّر الاتصال بالخادم حاليًا. يُرجى المحاولة بعد قليل." }));
    return () => {
      alive = false;
    };
  }, [q]);

  /** Show a passage (and optionally the block holding a quote) on the original page. */
  const show = useCallback(async (p: Passage, quote?: string, el?: HTMLElement | null, openSheet = false) => {
    const blocks = allBlocks(p);
    const target = quote ? blocksForQuote(blocks, quote) : (p.blocks ?? []).map((b) => b.id);
    const pageId = (target.length ? blocks.find((b) => b.id === target[0])?.page_id : null) ?? p.pages[0]?.id;
    if (!pageId) return;
    const pg = await loadPage(pageId);
    setPage(pg);
    setHl(target.length ? target : blocks.filter((b) => b.page_id === pageId).map((b) => b.id));
    setThreadFrom(el ?? null);
    if (openSheet && window.matchMedia("(max-width: 1023px)").matches) setSheet(true);
    setTimeout(() => viewer.current?.focusBlocks([]), 30);
  }, []);

  // Default page: the first passage (or, with ?thread=1, the first quote with its Source Thread).
  useEffect(() => {
    if (!data?.passages?.[0]) return;
    const pt = data.answer?.source_points[0];
    const p = pt ? data.passages[Number(pt.passage.replace(/\D/g, "")) - 1] : null;
    if (demoThread && pt && p) {
      setTimeout(() => show(p, pt.quote, firstPoint.current), 300);
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      show(data.passages[0]).then(() => setThreadFrom(null));
    }
  }, [data, show, demoThread]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSheet(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const byTag = (tag: string) => data?.passages[Number(tag.replace(/\D/g, "")) - 1];
  const pointHandlers = (pt: SourcePoint) => {
    const p = byTag(pt.passage);
    return {
      onMouseEnter: (e: React.MouseEvent<HTMLElement>) => p && show(p, pt.quote, e.currentTarget),
      onFocus: (e: React.FocusEvent<HTMLElement>) => p && show(p, pt.quote, e.currentTarget),
      onClick: (e: React.MouseEvent<HTMLElement>) => p && show(p, pt.quote, e.currentTarget, true),
      onMouseLeave: () => setThreadFrom(null),
      onBlur: () => setThreadFrom(null),
    };
  };
  /** Where a quote comes from: its block(s), page, author, hadith grading and verses. */
  const quoteInfo = (pt: SourcePoint) => {
    const p = byTag(pt.passage);
    if (!p) return null;
    const all = allBlocks(p);
    const ids = blocksForQuote(all, pt.quote);
    const b = all.find((x) => x.id === ids[0]);
    const origin = !b
      ? null
      : b.type === "footnote"
        ? "حاشية المحقق"
        : b.type === "editor_commentary" || b.author_role === "editor"
          ? "تعليق المحقق"
          : "متن الإمام النووي";
    const qn = norm(pt.quote);
    return {
      page: p.pages.find((x) => x.id === b?.page_id) ?? p.pages[0],
      origin,
      hadith: p.hadith?.find((h) => h.block_ids?.some((x) => ids.includes(x))) ?? null,
      verses: (p.quran ?? []).filter((v) => {
        if (!ids.includes(v.block_id)) return false;
        const vn = norm(v.printed_text);
        return qn.includes(vn) || vn.includes(qn) || vn.split(" ").filter((w) => qn.split(" ").includes(w)).length >= 3;
      }),
    };
  };

  const pagePane = page && (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span>
          الصفحة الأصلية · {t("page")} {ar(page.printed)}
        </span>
        <a className="text-insight underline" href={`/b/riyad1956/p/${page.printed}?hl=${hl.join(",")}`}>
          افتح في عارض المصدر ↗
        </a>
      </div>
      <PageViewer ref={viewer} page={page} highlight={hl} className="h-[min(74vh,1000px)]" />
    </div>
  );

  return (
    <main className="mx-auto grid w-full max-w-7xl flex-1 gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <section aria-label="الإجابة والنصوص" className="min-w-0">
        <SearchBox initial={q} />
        {!q && <p className="mt-6 text-muted">اكتب سؤالًا عن أبواب الإخلاص أو التوبة أو الصبر.</p>}
        {q && !data && !(err?.q === q) && (
          <div className="mt-6 rounded-xl border border-line bg-surface p-5">
            <StagedLoader />
          </div>
        )}
        {err?.q === q && <p role="alert" className="mt-6 text-madder">{err.msg}</p>}
        {data && (
          <div className="mt-6 grid gap-5">
            {data.quoted_verse_check && !data.quoted_verse_check.exact && (
              <section className="rounded-xl border border-amber/60 bg-amber/10 p-4" aria-label="تصحيح الآية">
                <h2 className="font-semibold text-amber-ink">تنبيه على نص الآية</h2>
                <p className="mt-1">
                  النص كما ورد في السؤال «{data.quoted_verse_check.printed_in_question}» لا يطابق لفظ المصحف.
                  {data.quoted_verse_check.candidates.length > 1 ? " أقرب الآيات إليه:" : " أقرب آية إليه:"}
                </p>
                <ul className="mt-2 grid gap-2">
                  {data.quoted_verse_check.candidates.map((c) => (
                    <li key={`${c.surah}:${c.ayah_start}`} className="rounded-lg border border-line bg-surface p-3">
                      <p className="quran-text text-xl">﴿{c.canonical_text}﴾</p>
                      <p className="mt-1 text-sm">
                        <a href={c.quranpedia_url} target="_blank" rel="noreferrer" className="text-insight underline">
                          سورة {c.surah_name} : {ar(c.ayah_start)}
                          {c.ayah_end !== c.ayah_start ? `–${ar(c.ayah_end)}` : ""} ↗
                        </a>
                        {" · "}
                        {c.in_corpus_pages.length
                          ? `مذكورة في الكتاب ص ${c.in_corpus_pages.map(ar).join("، ")}`
                          : "ليست في صفحات الكتاب المفهرسة؛ نصها من مصحف مجمع الملك فهد"}
                      </p>
                    </li>
                  ))}
                </ul>
                {data.quoted_verse_check.candidates.length > 1 && (
                  <p className="mt-2 text-sm">لا يمكن الجزم بأيّها المقصود؛ يُرجى الرجوع إلى النص الصحيح وعدم البناء على الصيغة الواردة في السؤال.</p>
                )}
              </section>
            )}

            {data.status === "answered" && data.answer && (
              <article className="rounded-xl border border-line bg-surface p-5 shadow-sm" aria-label="الإجابة">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold">{t("source_says")}</h2>
                  <LevelBadge level={data.level} />
                </div>
                <ul className="mt-3 grid gap-3">
                  {data.answer.source_points.map((pt, i) => {
                    const info = quoteInfo(pt);
                    const pg = info?.page;
                    const h = info?.hadith;
                    return (
                      <li key={i}>
                        <button
                          ref={i === 0 ? firstPoint : undefined}
                          {...pointHandlers(pt)}
                          className="group w-full rounded-lg p-2 text-start hover:bg-thread/10 focus:bg-thread/10"
                          aria-label={`عرض موضع النص في الصفحة ${pg ? ar(pg.printed) : ""}`}
                        >
                          {info?.origin && (
                            <span className={`mb-1 inline-block rounded px-1.5 py-0.5 text-xs ${info.origin === "متن الإمام النووي" ? "bg-thread/10 text-thread-strong" : "border border-line text-muted"}`}>
                              {info.origin}
                            </span>
                          )}
                          <span className="source-text block text-lg">
                            «{pt.quote}»{" "}
                            <span className="inline-block whitespace-nowrap rounded border border-thread/60 px-1.5 py-0.5 align-middle font-sans text-xs text-thread-strong">
                              {t("page")} {pg ? ar(pg.printed) : ""} ✓
                            </span>
                          </span>
                        </button>
                        {h && (
                          <div className="ps-2">
                            <HadithBadge h={h} />
                          </div>
                        )}
                        {info?.verses.map((v, k) => (
                          <div key={k} className="ps-2 pt-1">
                            <VerseChip q={v} />
                          </div>
                        ))}
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-4 border-t border-line pt-3">
                  <h3 className="text-sm font-medium text-muted">{t("clarification")}</h3>
                  <p className="mt-1 leading-loose text-foreground/85">
                    {(data.answer.explanation || data.answer.source_points.map((pt) => pt.text).join(" ")).replace(/\s*\[P\d+(?:\s*[,،]\s*P\d+)*\]/g, "")}
                  </p>
                </div>
                {data.answer.disagreement_noted && (
                  <p className="mt-2 text-sm text-amber-ink">في المسألة خلاف نقلته النصوص؛ عُرضت الأقوال دون ترجيح.</p>
                )}
                <details className="mt-4 text-sm">
                  <summary className="cursor-pointer text-thread-strong">
                    ✓ {ar(data.verification?.verified ?? 0)}/{ar(data.verification?.total ?? 0)} {t("verified_n")}
                  </summary>
                  <ul className="mt-2 grid gap-1 text-muted">
                    {(data.stages ?? []).map((s, i) => (
                      <li key={i}>
                        {s.stage}
                        {Object.entries(s)
                          .filter(([k]) => k !== "stage")
                          .map(([k, v]) => ` · ${k}: ${String(v)}`)
                          .join("")}
                      </li>
                    ))}
                    <li>{data.ai_notice}</li>
                  </ul>
                </details>
              </article>
            )}

            {data.status === "abstained" && (
              <section className="rounded-xl border border-line bg-surface p-5" aria-label="لا توجد إجابة كافية">
                <h2 className="text-lg font-semibold">لم يُعثَر في المصادر على ما يكفي للإجابة</h2>
                <p className="mt-2 leading-loose">{data.message}</p>
                <p className="mt-2 text-sm text-muted">
                  تُجيب هذه الأداة من صفحات الكتاب المفهرسة وحدها، ولا تؤلِّف إجابة من خارجها. وفيما يلي أقرب النصوص؛ وللاستزادة يُرجى سؤال
                  أهل العلم للتوسع.
                </p>
              </section>
            )}

            {data.status === "referral" && (
              <section className="rounded-xl border border-insight/40 bg-insight/5 p-5" aria-label="إحالة إلى أهل العلم">
                <h2 className="text-lg font-semibold">هذا السؤال يستلزم الرجوع إلى عالِم مؤهَّل</h2>
                <p className="mt-2 leading-loose">{data.message}</p>
              </section>
            )}

            {data.status === "unavailable" && (
              <section className="rounded-xl border border-line bg-surface p-5">
                <p>{data.message}</p>
              </section>
            )}

            {data.passages?.length > 0 && (
              <section aria-label={t("passages")}>
                <h2 className="mb-3 text-lg font-semibold">
                  {data.status === "answered" ? t("passages") : "أقرب النصوص من الكتاب"}
                </h2>
                <div className="grid gap-3">
                  {data.passages.map((p, i) => (
                    <PassageCard key={p.id} p={p} tag={`P${i + 1}`} onShow={() => show(p, undefined, null, true)} />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </section>

      {/* Page pane (desktop) */}
      <aside aria-label="الصفحة الأصلية" className="hidden lg:block">
        <div className="sticky top-16">{pagePane}</div>
      </aside>

      {/* Bottom sheet (mobile) */}
      {sheet && page && (
        <div role="dialog" aria-modal="true" aria-label="الصفحة الأصلية" className="fixed inset-0 z-50 flex items-end bg-black/40 lg:hidden" onClick={() => setSheet(false)}>
          <div className="max-h-[88vh] w-full overflow-auto rounded-t-2xl bg-background p-3" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex justify-between">
              <span className="mx-auto h-1.5 w-12 rounded bg-line" aria-hidden />
              <button onClick={() => setSheet(false)} className="rounded border border-line px-2 text-sm">
                إغلاق
              </button>
            </div>
            {pagePane}
          </div>
        </div>
      )}
      <SourceThread from={threadFrom} to={() => viewer.current?.highlightEl() ?? null} />
    </main>
  );
}
