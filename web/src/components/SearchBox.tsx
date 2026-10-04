"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useT } from "@/lib/i18n";

// Real example questions about the indexed chapters (rotating placeholder).
export const EXAMPLES = [
  "ما شروط التوبة؟",
  "ما فضل الصبر عند المصيبة؟",
  "ما معنى «إنما الأعمال بالنيات»؟",
  "هل يقبل الله التوبة في آخر العمر؟",
  "ما المقصود بالإخلاص في العمل؟",
];

export function SearchBox({ initial = "", big = false }: { initial?: string; big?: boolean }) {
  const t = useT();
  const router = useRouter();
  const [q, setQ] = useState(initial);
  const [ph, setPh] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const id = setInterval(() => setPh((i) => (i + 1) % EXAMPLES.length), 3500);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearInterval(id);
      window.removeEventListener("keydown", onKey);
    };
  }, []);
  return (
    <form
      role="search"
      className="flex w-full gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (q.trim().length >= 3) router.push(`/ask?q=${encodeURIComponent(q.trim())}`);
      }}
    >
      <label htmlFor="q" className="sr-only">
        {t("search_ph")}
      </label>
      <input
        id="q"
        ref={input}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={EXAMPLES[ph]}
        className={`min-w-0 flex-1 rounded-xl border border-line bg-surface px-4 shadow-sm placeholder:text-muted/70 ${big ? "py-4 text-xl" : "py-2.5 text-base"}`}
        autoComplete="off"
      />
      <button type="submit" className={`rounded-xl bg-ink px-5 font-medium text-paper ${big ? "text-lg" : ""}`}>
        {t("ask")}
      </button>
    </form>
  );
}
