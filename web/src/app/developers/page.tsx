"use client";

import { useState } from "react";

const BASE = "https://<your-asool-api>";

const ENDPOINTS = [
  {
    method: "GET",
    path: "/api/v1/search?q=شروط التوبة&k=3",
    desc: "بحث هجين (كلمات + معنى) في الكتاب المفهرس. كل نتيجة تحمل توثيق الصفحة والمربعات المحيطة بكتلها على صورة الصفحة الأصلية.",
    example: `{
  "query": "شروط التوبة",
  "results": [{
    "id": "riyad1956-c013",
    "kind": "matn",
    "author_label": "متن الإمام النووي",
    "breadcrumb": ["رياض الصالحين", "باب التوبة"],
    "text": "قال العلماء : التوبةُ(١) واجبةٌ منْ كلِّ ذنبٍ …",
    "pages": [{"id": "riyad1956-p018", "printed": 18,
               "citation": "رياض الصالحين، الإمام يحيى بن شرف النووي، …، ص 18"}],
    "blocks": [{"id": "riyad1956-p018-b03", "type": "body",
                "bbox": [412, 640, 1760, 1488], "bbox_source": "fusion"}],
    "footnotes": [{"footnote_marker": "(١)", "text": "القرب إلى الله بالطاعة …"}],
    "quran": [], "hadith": []
  }],
  "attribution": "Asool (أصول) — رياض الصالحين، طبعة 1956. Cite the printed page."
}`,
  },
  {
    method: "GET",
    path: "/api/v1/passages/riyad1956-c013",
    desc: "نص كامل لمقطع مع كتله وحواشيه وفحص الآيات وحكم الأحاديث ومواضعها في الصفحات.",
    example: `{ "id": "riyad1956-c013", "kind": "matn", "pages": [...], "blocks": [...], "footnotes": [...] }`,
  },
];

export default function Developers() {
  const [copied, setCopied] = useState("");
  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <h1 className="text-3xl font-semibold">للمطورين</h1>
      <p className="mt-2 leading-relaxed text-muted">
        واجهة قراءة عامة مجانية لمنصات المحتوى الإسلامي ومراكز البحث وتطبيقات الذكاء الاصطناعي: ابنِ على نص موثق يعود كل مقطع فيه إلى صفحته المطبوعة.
      </p>
      <dl className="mt-6 grid gap-2 text-sm sm:grid-cols-3">
        <div className="rounded-lg border border-line bg-surface p-3">
          <dt className="text-muted">الصيغة</dt>
          <dd>JSON · قراءة فقط · بلا مفتاح</dd>
        </div>
        <div className="rounded-lg border border-line bg-surface p-3">
          <dt className="text-muted">التوثيق التفصيلي</dt>
          <dd>
            <code dir="ltr">/docs</code> (OpenAPI)
          </dd>
        </div>
        <div className="rounded-lg border border-line bg-surface p-3">
          <dt className="text-muted">الشرط</dt>
          <dd>اذكر الكتاب والطبعة ورقم الصفحة عند العرض</dd>
        </div>
      </dl>
      {ENDPOINTS.map((e) => {
        const curl = `curl "${BASE}${e.path}"`;
        return (
          <section key={e.path} className="mt-8">
            <h2 className="font-mono text-lg" dir="ltr">
              <span className="rounded bg-thread/20 px-1.5 text-sm">{e.method}</span> {e.path}
            </h2>
            <p className="mt-1 text-sm">{e.desc}</p>
            <div className="mt-2 flex items-start gap-2">
              <pre className="flex-1 overflow-x-auto rounded-lg bg-ink p-3 text-sm text-paper" dir="ltr">
                {curl}
              </pre>
              <button
                className="rounded border border-line px-2 py-1 text-xs"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(curl);
                    setCopied(e.path);
                  } catch {
                    /* clipboard blocked */
                  }
                }}
              >
                {copied === e.path ? "✓ نُسخ" : "نسخ"}
              </button>
            </div>
            <pre className="mt-2 max-h-80 overflow-auto rounded-lg border border-line bg-surface p-3 text-xs" dir="ltr">
              {e.example}
            </pre>
          </section>
        );
      })}
      <section className="mt-8 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">الحدود والاستخدام العادل</h2>
        <ul className="mt-2 list-disc space-y-1 ps-5">
          <li>نقاط البحث والمقاطع لا تستدعي نماذج لغوية مولِّدة؛ نقطة الإجابة الداخلية محدودة لكل عنوان IP (٢٠ إجابة جديدة في الساعة).</li>
          <li>النصوص منقولة حرفيًا من الطبعة المطبوعة؛ لا تُعدَّل، والحواشي من تعليق المحقق مصطفى محمد عمارة.</li>
          <li>لا نجمع بيانات شخصية ولا نتتبع المستخدمين.</li>
        </ul>
      </section>
    </main>
  );
}
