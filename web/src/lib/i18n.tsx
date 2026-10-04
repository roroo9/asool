"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Lang = "ar" | "en";

const S = {
  brand: { ar: "أصول", en: "Asool" },
  tagline: {
    ar: "من صفحات الكتب الموثوقة إلى معرفة يمكن التحقق منها",
    en: "From trusted printed pages to knowledge you can verify",
  },
  honest: {
    ar: "أداة بحث مدعومة بالذكاء الاصطناعي، كل نتيجة مرتبطة بموضعها في الصفحة الأصلية",
    en: "An AI-assisted research tool. Every result is linked to its place on the original page.",
  },
  nav_ask: { ar: "اسأل", en: "Ask" },
  nav_book: { ar: "الكتاب", en: "Book" },
  nav_compare: { ar: "المقارنة", en: "Compare" },
  nav_proof: { ar: "البرهان", en: "Proof" },
  nav_review: { ar: "المراجعة", en: "Review" },
  nav_how: { ar: "كيف يعمل", en: "How it works" },
  nav_dev: { ar: "للمطورين", en: "Developers" },
  search_ph: { ar: "اسأل عن الإخلاص أو التوبة أو الصبر…", en: "Ask about sincerity, repentance or patience…" },
  ask: { ar: "اسأل", en: "Ask" },
  source_says: { ar: "ما في المصدر", en: "What the source says" },
  clarification: { ar: "توضيح", en: "Clarification" },
  ai_generated: { ar: "من توليد النموذج", en: "AI-generated" },
  verified_n: { ar: "اقتباسات تم التحقق منها حرفيًا", en: "quotes verified word for word" },
  passages: { ar: "النصوص من الكتاب", en: "Passages from the book" },
  page: { ar: "ص", en: "p." },
  open_page: { ar: "افتح الصفحة الأصلية", en: "Open the original page" },
  xray: { ar: "الأشعة", en: "X-ray" },
  footnotes: { ar: "الحواشي", en: "Footnotes" },
  copy_cite: { ar: "نسخ مع التوثيق", en: "Copy with citation" },
  copied: { ar: "نُسخ", en: "Copied" },
  prev: { ar: "السابقة", en: "Previous" },
  next: { ar: "التالية", en: "Next" },
  theme: { ar: "المظهر", en: "Theme" },
  lang_toggle: { ar: "English", en: "العربية" },
  editor_label: { ar: "تعليق المحقق مصطفى محمد عمارة", en: "Editor's commentary (Mustafa M. Amara)" },
  matn_label: { ar: "متن الإمام النووي", en: "Imam al-Nawawi's text" },
  level: { ar: "مستوى المحتوى", en: "Content level" },
  stage_search: { ar: "البحث في المصادر", en: "Searching the sources" },
  stage_verify: { ar: "التحقق من الاقتباسات", en: "Verifying quotes" },
  stage_compose: { ar: "صياغة الإجابة", en: "Composing" },
} as const;

export type Key = keyof typeof S;

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({
  lang: "ar",
  setLang: () => {},
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("ar");
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("asool.lang");
    } catch {
      /* storage unavailable */
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved === "en") setLangState("en");
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("asool.lang", l);
    } catch {
      /* ignore */
    }
  };
  return <Ctx.Provider value={{ lang, setLang }}>{children}</Ctx.Provider>;
}

export function useLang() {
  return useContext(Ctx);
}

export function useT() {
  const { lang } = useContext(Ctx);
  return (k: Key) => S[k][lang];
}
