"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  getReviewer,
  getToken,
  saveIdentity,
  toArabicDigits,
  type Progress,
} from "@/lib/review";

export default function GoldIndex() {
  const [pages, setPages] = useState<Progress[] | null>(null);
  const [error, setError] = useState("");
  const [token, setToken] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(() => {
    setError("");
    api<Progress[]>("/pages")
      .then(setPages)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    // Read the remembered identity once on mount (localStorage is browser-only).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(getToken());
    setName(getReviewer());
    load();
  }, [load]);

  const totals = (pages ?? []).reduce(
    (a, p) => ({
      done: a.done + p.items_done + p.spot_done,
      all: a.all + p.items_total + p.spot_total,
    }),
    { done: 0, all: 0 },
  );

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 className="text-3xl font-semibold">مراجعة مجموعة المرجع (Gold set)</h1>
      <p className="mt-3 max-w-2xl leading-relaxed opacity-80">
        ثلاث قراءات مستقلة لكل صفحة. الكلمات التي اتفقت عليها القراءات الثلاث قُبلت
        تلقائيًا. يُعرض عليك هنا موضع الخلاف فقط، مع صورة السطر من الصفحة الأصلية.
      </p>

      <form
        className="mt-6 flex flex-wrap items-end gap-4 rounded-lg border border-ink/15 bg-paper p-4"
        onSubmit={(e) => {
          e.preventDefault();
          saveIdentity(token.trim(), name.trim());
          load();
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          اسم المراجِع
          <input
            className="rounded border border-ink/25 bg-background px-3 py-2"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          رمز الدخول
          <input
            className="rounded border border-ink/25 bg-background px-3 py-2"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            dir="ltr"
          />
        </label>
        <button className="rounded bg-ink px-4 py-2 text-paper" type="submit">
          حفظ
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-4 text-madder">
          {error}. تأكد من رمز الدخول ثم اضغط «حفظ».
        </p>
      )}

      {pages && (
        <>
          <p className="mt-8 text-sm">
            التقدم الكلي: {toArabicDigits(totals.done)} من {toArabicDigits(totals.all)}
          </p>
          <div
            className="mt-2 h-2 w-full overflow-hidden rounded bg-ink/10"
            role="progressbar"
            aria-valuenow={totals.done}
            aria-valuemax={totals.all}
          >
            <div
              className="h-full bg-thread"
              style={{ width: `${totals.all ? (100 * totals.done) / totals.all : 0}%` }}
            />
          </div>
          <ul className="mt-6 divide-y divide-ink/10 rounded-lg border border-ink/15">
            {pages.map((p) => {
              const done = p.items_done + p.spot_done;
              const all = p.items_total + p.spot_total;
              return (
                <li key={p.page_id} className="flex items-center justify-between gap-4 p-4">
                  <div>
                    <Link
                      href={`/review/gold/${p.page_id}`}
                      className="text-lg font-medium text-insight underline-offset-4 hover:underline"
                    >
                      صفحة {toArabicDigits(p.printed)}
                    </Link>
                    <p className="text-sm opacity-70">
                      قُبل تلقائيًا {toArabicDigits(p.auto_accepted)} من{" "}
                      {toArabicDigits(p.total_tokens)} كلمة
                    </p>
                  </div>
                  <span className="text-sm">
                    {p.finalized ? (
                      <span className="text-thread">✓ اعتُمدت</span>
                    ) : (
                      `${toArabicDigits(done)} / ${toArabicDigits(all)}`
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </main>
  );
}
