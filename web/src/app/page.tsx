"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SearchBox } from "@/components/SearchBox";
import { ar, getJSON, imageUrl } from "@/lib/api";
import { useT } from "@/lib/i18n";

type Book = {
  id: string;
  title_ar: string;
  author_ar: string;
  edition: string;
  editor_ar: string;
  page_count: number;
  page_ids: string[];
};

export default function Home() {
  const t = useT();
  const [book, setBook] = useState<Book | null>(null);
  useEffect(() => {
    getJSON<Book[]>("/books")
      .then((b) => setBook(b[0]))
      .catch(() => {});
  }, []);
  return (
    <main className="flex-1">
      {/* Hero: a softly lit real page behind the search field */}
      <section className="relative isolate overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl("riyad1956-p041")}
          alt=""
          aria-hidden
          className="absolute inset-x-0 top-0 -z-10 mx-auto h-[130%] w-auto max-w-none opacity-[0.13] [mask-image:radial-gradient(ellipse_at_center,black_35%,transparent_75%)] dark:opacity-[0.10] dark:invert"
        />
        <div className="mx-auto flex max-w-3xl flex-col items-center px-4 pb-16 pt-20 text-center sm:pt-28">
          <h1 className="font-source text-6xl font-bold sm:text-7xl">{t("brand")}</h1>
          <p className="mt-4 text-lg text-muted sm:text-xl">{t("tagline")}</p>
          <div className="mt-8 w-full">
            <SearchBox big />
          </div>
          <p className="mt-4 text-sm text-muted">{t("honest")}</p>
          <p className="mt-1 text-xs text-muted">
            اضغط <kbd className="rounded border border-line px-1">/</kbd> للبحث
          </p>
        </div>
      </section>

      {/* Library: the book as a physical spine */}
      <section aria-label="المكتبة" className="mx-auto max-w-5xl px-4">
        <h2 className="text-sm font-medium text-muted">في المكتبة</h2>
        <div className="mt-3 flex flex-wrap gap-4">
          <Link
            href="/b/riyad1956/p/12"
            className="group flex w-full max-w-md items-stretch overflow-hidden rounded-lg border border-line bg-surface shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
          >
            <span className="w-3 bg-[#7a2e1f]" aria-hidden />
            <span className="w-1 bg-[#c9a54a]" aria-hidden />
            <span className="flex-1 p-4 text-start">
              <span className="font-source block text-2xl font-bold">{book?.title_ar ?? "رياض الصالحين"}</span>
              <span className="block text-sm">{book?.author_ar ?? "الإمام يحيى بن شرف النووي (ت 676هـ)"}</span>
              <span className="mt-2 block text-xs text-muted">
                {book?.edition ?? "دار إحياء الكتب العربية، القاهرة، 1956"} · شرح الغريب: {book?.editor_ar ?? "مصطفى محمد عمارة"}
              </span>
              <span className="mt-2 block text-xs text-muted">
                {book ? `${ar(book.page_count)} صفحة مفهرسة: باب الإخلاص، باب التوبة، باب الصبر` : "…"}
              </span>
            </span>
          </Link>
        </div>
      </section>

      {/* What Asool does, in three honest lines */}
      <section className="mx-auto mt-12 grid max-w-5xl gap-6 px-4 sm:grid-cols-3">
        {[
          ["يعيدك إلى الصفحة", "كل نص وكل اقتباس مرتبط بموضعه المظلل في صورة الصفحة المطبوعة."],
          ["يتحقق قبل أن يقول", "الاقتباسات تُطابق حرفيًا مع الكتاب، والآيات مع مصحف مجمع الملك فهد، وما لا يثبت يُحذف."],
          ["يمتنع ويحيل", "إذا لم يجد ما يكفي امتنع، وإذا كان السؤال فتوى شخصية أحال إلى أهل العلم."],
        ].map(([h, p]) => (
          <div key={h}>
            <h3 className="font-semibold">{h}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted">{p}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
