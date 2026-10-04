"use client";

import { useState } from "react";
import { ar } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Hadith, QuranRef } from "@/lib/types";

export function QuranCheck({ q }: { q: QuranRef }) {
  const exact = q.match_type === "exact";
  const url = q.quranpedia_url ?? `https://quranpedia.net/surah/${q.surah}/${q.ayah_start}`;
  const range = q.ayah_end !== q.ayah_start ? `${ar(q.ayah_start)}–${ar(q.ayah_end)}` : ar(q.ayah_start);
  return (
    <div className="rounded-md border border-line bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-0.5 font-medium ${exact ? "bg-thread/20 text-thread-strong" : q.match_type === "minor_variant" ? "bg-amber/25 text-amber-ink" : "bg-madder/15 text-madder"}`}
        >
          {exact ? "✓ مطابقة للمصحف" : q.match_type === "minor_variant" ? "⚠ فرق يسير" : "✗ لا تطابق المصحف"}
        </span>
        <a href={url} target="_blank" rel="noreferrer" className="rounded border border-line px-2 py-0.5 text-insight">
          سورة {ar(q.surah)}: {range} ↗
        </a>
      </div>
      {!exact && q.diff_ops.length > 0 && (
        <ul className="mt-2 grid gap-1">
          {q.diff_ops.map((o, i) => (
            <li key={i}>
              المطبوع: <span className="font-source text-madder">{o.printed.join(" ") || "—"}</span> · في المصحف:{" "}
              <span className="font-source text-thread-strong">{o.reference.join(" ") || "—"}</span>
            </li>
          ))}
        </ul>
      )}
      <details className="mt-2">
        <summary className="cursor-pointer text-muted">نص المصحف (رواية حفص، مجمع الملك فهد)</summary>
        <p className="quran-text mt-1 text-lg">{q.canonical_text}</p>
        <p className="mt-1 text-xs text-muted">لم يُغيَّر النص المطبوع؛ نص المصحف معروض بجانبه للمقارنة فقط.</p>
      </details>
    </div>
  );
}

export function HadithGrade({ h }: { h: Hadith }) {
  const ok = ["in_sahihayn", "hadeethenc", "dorar_manual"].includes(h.grading_status);
  return (
    <div className="rounded-md border border-line bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-0.5 font-medium ${ok ? "bg-thread/20 text-thread-strong" : "bg-amber/25 text-amber-ink"}`}>
          {ok ? "✓ " : "⚠ "}
          {h.grading}
        </span>
        {h.grading_source_url && (
          <a className="text-insight underline" href={h.grading_source_url} target="_blank" rel="noreferrer">
            {h.grading_source ?? "المصدر"} ↗
          </a>
        )}
        {!h.grading_source_url && h.grading_source && <span className="text-muted">{h.grading_source}</span>}
      </div>
      <p className="mt-1">
        تخريج الإمام النووي كما طُبع: <strong>{h.takhrij_printed ?? "غير موجود في صفحات المدونة"}</strong>
      </p>
      <a className="mt-1 inline-block text-xs text-insight underline" href={h.dorar_search_url} target="_blank" rel="noreferrer">
        ابحث عنه في الدرر السنية ↗
      </a>
    </div>
  );
}

export function CopyCitation({ text, citation }: { text: string; citation: string }) {
  const t = useT();
  const [done, setDone] = useState(false);
  return (
    <button
      className="rounded border border-line px-2 py-0.5 text-xs"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(`«${text}»\n— ${citation}`);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* clipboard blocked */
        }
      }}
    >
      {done ? `✓ ${t("copied")}` : t("copy_cite")}
    </button>
  );
}

export function LevelBadge({ level }: { level: string | null }) {
  if (!level) return null;
  const tip: Record<string, string> = {
    A: "معلومات أصلية مستقرة: إجابة مباشرة موثقة بالمصدر",
    B: "شرح وتعريف واستدلال: من المادة المعتمدة مع إظهار المرجع",
    C: "مسألة خلافية أو عالية الحساسية: إجابة مقيدة مع بيان وجود الخلاف والإحالة",
    D: "فتوى أو حالة شخصية: لا يُصدر النظام حكمًا ويحيل إلى جهة مؤهلة",
  };
  return (
    <span title={tip[level]} className="rounded border border-line px-2 py-0.5 text-xs">
      مستوى المحتوى: {level === "A" ? "أ" : level === "B" ? "ب" : level === "C" ? "ج" : "د"}
    </span>
  );
}
