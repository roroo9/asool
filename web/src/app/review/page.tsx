"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ar, getJSON, imageUrl } from "@/lib/api";
import { getReviewer, getToken, type Progress } from "@/lib/review";

type Item = {
  id: number;
  block_id: string | null;
  page_id: string;
  reason: string;
  confidence: number | null;
  resolved: number;
  resolved_by: string | null;
  type: string | null;
  text_raw: string | null;
  bbox: number[] | null;
  regions?: { bbox: number[] }[];
};

const W = 2146;
const H = 3025;

function Thumb({ pageId, box }: { pageId: string; box: number[] | null }) {
  if (!box) return null;
  const pad = 40;
  const [x0, y0, x1, y1] = [box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad];
  const w = x1 - x0;
  const h = Math.max(y1 - y0, 60);
  const scale = 260 / w;
  return (
    <div
      role="img"
      aria-label="مقتطف من الصفحة الأصلية"
      className="overflow-hidden rounded border border-line bg-white"
      style={{
        width: 260,
        height: Math.min(140, h * scale),
        backgroundImage: `url(${imageUrl(pageId)})`,
        backgroundSize: `${W * scale}px ${H * scale}px`,
        backgroundPosition: `${-x0 * scale}px ${-y0 * scale}px`,
      }}
    />
  );
}

export default function ReviewPage() {
  const [items, setItems] = useState<Item[] | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [gold, setGold] = useState<Progress[] | null>(null);
  const [msg, setMsg] = useState("");
  const load = useCallback(() => {
    getJSON<Item[]>(`/review?include_resolved=${showResolved}`).then(setItems).catch(() => setItems([]));
  }, [showResolved]);
  useEffect(load, [load]);
  useEffect(() => {
    fetch("/api/review/gold/pages", { headers: { "x-review-token": getToken() } })
      .then((r) => (r.ok ? r.json() : null))
      .then(setGold)
      .catch(() => {});
  }, []);

  const resolve = async (id: number) => {
    const r = await fetch(`/api/review/${id}/resolve`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-review-token": getToken() },
      body: JSON.stringify({ reviewer: getReviewer() || "reviewer", note: "مراجَع" }),
    });
    setMsg(r.ok ? "وُضعت علامة المراجعة." : "يلزم رمز المراجعة (من صفحة مراجعة مجموعة المرجع).");
    load();
  };

  const done = gold?.reduce((a, p) => a + p.items_done + p.spot_done, 0) ?? 0;
  const all = gold?.reduce((a, p) => a + p.items_total + p.spot_total, 0) ?? 0;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
      <h1 className="text-3xl font-semibold">المراجعة البشرية</h1>
      <p className="mt-2 max-w-3xl leading-relaxed text-muted">
        ما يشك فيه النظام لا يُخفى: الكتل منخفضة الثقة، والحواشي غير المربوطة، والآيات المختلفة عن المصحف، والصفحات التي لم يغطّها النص المستخرج كاملًا تظهر هنا حتى يراجعها إنسان.
      </p>

      <section className="mt-6 grid gap-3 sm:grid-cols-2">
        <Link href="/review/gold" className="rounded-xl border border-line bg-surface p-4 hover:border-insight">
          <h2 className="font-semibold">مراجعة مجموعة المرجع</h2>
          <p className="mt-1 text-sm text-muted">ثلاث قراءات مستقلة لكل صفحة؛ تُعرض مواضع الخلاف فقط.</p>
          {gold && (
            <p className="mt-2 text-sm">
              التقدم: {ar(done)} / {ar(all)}
            </p>
          )}
        </Link>
        <Link href="/review/hadith" className="rounded-xl border border-line bg-surface p-4 hover:border-insight">
          <h2 className="font-semibold">أحكام الأحاديث</h2>
          <p className="mt-1 text-sm text-muted">ما خرّجه المصنف من غير الصحيحين: مطابقة الموسوعة الحديثية أو إدخال الحكم من الدرر السنية.</p>
        </Link>
      </section>

      <section className="mt-8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-semibold">قائمة التنبيهات</h2>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
            إظهار ما رُوجع
          </label>
        </div>
        {msg && <p role="status" className="mt-2 text-sm">{msg}</p>}
        {items && items.length === 0 && <p className="mt-4 rounded-lg border border-dashed border-line p-4 text-muted">لا توجد تنبيهات مفتوحة. كل الصفحات المفهرسة رُوجعت.</p>}
        <ul className="mt-4 grid gap-3">
          {items?.map((it) => {
            const printed = Number(it.page_id.split("-p")[1]);
            const box = it.bbox ?? it.regions?.[0]?.bbox ?? null;
            return (
              <li key={it.id} className="flex flex-wrap gap-4 rounded-xl border border-line bg-surface p-4">
                <Thumb pageId={it.page_id} box={box} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-muted">
                    صفحة {ar(printed)} · {it.block_id ? "كتلة" : "الصفحة كاملة"}
                    {it.confidence != null && ` · الثقة ${ar(Math.round(it.confidence * 100))}٪`}
                  </p>
                  <p className="mt-1">{it.reason}</p>
                  {it.text_raw && <p className="source-text mt-1 line-clamp-2 text-sm">{it.text_raw}</p>}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Link href={`/b/riyad1956/p/${printed}?xray=1${it.block_id ? `&hl=${it.block_id}` : ""}`} className="rounded border border-line px-2 py-1 text-sm text-insight">
                      افتح في عارض المصدر
                    </Link>
                    {it.resolved ? (
                      <span className="rounded bg-thread/20 px-2 py-1 text-sm">✓ {it.resolved_by}</span>
                    ) : (
                      <button onClick={() => resolve(it.id)} className="rounded bg-ink px-2 py-1 text-sm text-paper">
                        وضع علامة: رُوجع
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}
