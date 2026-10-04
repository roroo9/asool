"use client";

import Link from "next/link";
import { CopyCitation, HadithGrade, QuranCheck } from "@/components/Bits";
import { ar } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Passage } from "@/lib/types";

function Highlighted({ text, spans }: { text: string; spans: number[][] }) {
  if (!spans?.length) return <>{text}</>;
  const out: React.ReactNode[] = [];
  let last = 0;
  spans.forEach(([a, b], i) => {
    if (a > last) out.push(text.slice(last, a));
    out.push(
      <mark key={i} className="rounded bg-thread/25 px-0.5 text-inherit">
        {text.slice(a, b)}
      </mark>,
    );
    last = b;
  });
  out.push(text.slice(last));
  return <>{out}</>;
}

export function PassageCard({
  p,
  tag,
  onShow,
  active,
}: {
  p: Passage;
  tag?: string;
  onShow?: () => void;
  active?: boolean;
}) {
  const t = useT();
  const editor = p.kind === "editor_commentary";
  const first = p.pages[0];
  return (
    <article
      className={`rounded-xl border p-4 ${active ? "border-thread" : "border-line"} ${editor ? "bg-[color-mix(in_oklab,var(--surface),#8b5a2b_6%)]" : "bg-surface"}`}
    >
      <header className="flex flex-wrap items-center gap-2 text-xs text-muted">
        {tag && <span className="rounded bg-ink px-1.5 py-0.5 font-medium text-paper">{tag}</span>}
        <span className={editor ? "font-medium text-[#8b5a2b] dark:text-[#d9a777]" : "font-medium"}>
          {editor ? t("editor_label") : t("matn_label")}
        </span>
        {p.breadcrumb && <span>· {p.breadcrumb.slice(1).join(" › ")}</span>}
        <span className="ms-auto flex flex-wrap gap-1">
          {p.pages.map((pg) => (
            <Link
              key={pg.id}
              href={`/b/riyad1956/p/${pg.printed}?hl=${(p.blocks ?? []).filter((b) => b.page_id === pg.id).map((b) => b.id).join(",")}`}
              className="rounded border border-line px-1.5 py-0.5 text-insight"
            >
              {t("page")} {ar(pg.printed)}
            </Link>
          ))}
        </span>
      </header>
      <p className="source-text mt-2 line-clamp-6 text-lg">
        <Highlighted text={p.text} spans={p.highlights ?? []} />
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {onShow && (
          <button onClick={onShow} className="rounded border border-line px-2 py-0.5 text-xs">
            {t("open_page")}
          </button>
        )}
        {first?.citation && <CopyCitation text={p.text} citation={first.citation} />}
      </div>
      {(p.quran?.length ?? 0) > 0 && (
        <div className="mt-3 grid gap-2">
          {p.quran!.map((q, i) => (
            <QuranCheck key={i} q={q} />
          ))}
        </div>
      )}
      {(p.hadith?.length ?? 0) > 0 && (
        <div className="mt-3 grid gap-2">
          {p.hadith!.map((h) => (
            <HadithGrade key={h.id} h={h} />
          ))}
        </div>
      )}
      {(p.footnotes?.length ?? 0) > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-muted">
            {t("footnotes")} ({ar(p.footnotes!.length)}) · {t("editor_label")}
          </summary>
          <ul className="mt-1 grid gap-1">
            {p.footnotes!.map((f) => (
              <li key={f.id} className="source-text">
                {f.text}
                {f.attached_text?.map((a, i) => (
                  <span key={i} className="block ps-4 text-muted">
                    {a}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
