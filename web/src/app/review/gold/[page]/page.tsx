"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  BLOCK_TYPES,
  cropUrl,
  pageUrl,
  getReviewer,
  toArabicDigits,
  type Draft,
  type Located,
  type Progress,
} from "@/lib/review";

type Mode = "items" | "spot" | "structure";

export default function GoldPage() {
  const { page } = useParams<{ page: string }>();
  const [d, setD] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("items");
  const [idx, setIdx] = useState(0);
  const [editState, setEditState] = useState<{ id: string; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const editRef = useRef<HTMLInputElement>(null);
  const reviewer = typeof window === "undefined" ? "" : getReviewer();

  const firstOpen = (x: Draft): [Mode, number] => {
    const i = x.review_items.findIndex((it) => it.decision === null);
    if (i >= 0) return ["items", i];
    const s = x.spotcheck.findIndex((it) => it.verdict === null);
    if (s >= 0) return ["spot", s];
    return ["structure", 0];
  };

  useEffect(() => {
    api<Draft>(`/${page}`)
      .then((x) => {
        setD(x);
        // ?item=<id> opens a specific dispute or spot-check (useful for re-checks).
        const want = new URLSearchParams(window.location.search).get("item");
        const ri = want ? x.review_items.findIndex((it) => it.id === want) : -1;
        const si = want ? x.spotcheck.findIndex((it) => it.id === want) : -1;
        if (ri >= 0) {
          setMode("items");
          setIdx(ri);
        } else if (si >= 0) {
          setMode("spot");
          setIdx(si);
        } else {
          const [m, i] = firstOpen(x);
          setMode(m);
          setIdx(i);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, [page]);

  const item = mode === "items" ? d?.review_items[idx] : undefined;
  const spot = mode === "spot" ? d?.spotcheck[idx] : undefined;

  // The edit box defaults to the saved decision or the best-supported candidate,
  // and keeps the reviewer's typing only while the same item is shown.
  const currentId = item?.id ?? spot?.id ?? "";
  const defaultEdit = item
    ? (item.decision ?? item.candidates[0]?.text ?? "")
    : spot
      ? (spot.fix ?? spot.text)
      : "";
  const edit = editState && editState.id === currentId ? editState.text : defaultEdit;
  const setEdit = (text: string) => setEditState({ id: currentId, text });

  const context = useMemo(() => {
    if (!d || !item) return null;
    const toks = d.tokens;
    const from = Math.max(0, item.tok_from - 8);
    const to = Math.min(toks.length, item.tok_to + 8);
    return {
      before: toks.slice(from, item.tok_from).map((t) => t.raw).join(" "),
      after: toks.slice(item.tok_to, to).map((t) => t.raw).join(" "),
    };
  }, [d, item]);

  const applyProgress = (p: Progress) => setD((x) => (x ? { ...x, progress: p } : x));

  const advance = useCallback(
    (next: Draft) => {
      const list = mode === "items" ? next.review_items : next.spotcheck;
      if (idx + 1 < list.length) {
        setIdx(idx + 1);
      } else {
        const [m, i] = firstOpen(next);
        setMode(m);
        setIdx(i);
      }
    },
    [idx, mode],
  );

  const decide = useCallback(
    async (text: string) => {
      if (!d || !item || saving) return;
      setSaving(true);
      try {
        const p = await api<Progress>(`/${page}/item/${item.id}`, { text, reviewer });
        const next = {
          ...d,
          review_items: d.review_items.map((it) =>
            it.id === item.id ? { ...it, decision: text.trim() } : it,
          ),
          progress: p,
        };
        setD(next);
        advance(next);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setSaving(false);
      }
    },
    [d, item, page, reviewer, saving, advance],
  );

  const judge = useCallback(
    async (verdict: "ok" | "wrong", fix?: string) => {
      if (!d || !spot || saving) return;
      setSaving(true);
      try {
        const p = await api<Progress>(`/${page}/spot/${spot.id}`, {
          verdict,
          fix: fix ?? null,
          reviewer,
        });
        const next = {
          ...d,
          spotcheck: d.spotcheck.map((s) =>
            s.id === spot.id ? { ...s, verdict, fix: fix ?? null } : s,
          ),
          progress: p,
        };
        setD(next);
        advance(next);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setSaving(false);
      }
    },
    [d, spot, page, reviewer, saving, advance],
  );

  // Keyboard shortcuts: 1-3 choose, Enter saves the edit box, E edits,
  // D deletes the span, arrows move, Y/N for spot checks.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const inEdit = document.activeElement === editRef.current;
      if (inEdit) {
        if (e.key === "Enter") {
          e.preventDefault();
          if (item) decide(edit);
          if (spot) judge(edit.trim() === spot.text ? "ok" : "wrong", edit.trim());
        } else if (e.key === "Escape") {
          editRef.current?.blur();
        }
        return;
      }
      if (item) {
        const n = Number(e.key);
        if (n >= 1 && n <= item.candidates.length) decide(item.candidates[n - 1].text);
        else if (e.key === "Enter") decide(edit);
        else if (e.key.toLowerCase() === "d") decide("");
      }
      if (spot) {
        if (e.key.toLowerCase() === "y") judge("ok");
        if (e.key.toLowerCase() === "n") editRef.current?.focus();
      }
      if (e.key.toLowerCase() === "e") {
        e.preventDefault();
        editRef.current?.focus();
        editRef.current?.select();
      }
      // RTL: the left arrow moves forward, the right arrow moves back.
      if (e.key === "ArrowLeft") setIdx((i) => i + 1);
      if (e.key === "ArrowRight") setIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, spot, edit, decide, judge]);

  if (error)
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p role="alert" className="text-madder">
          {error}
        </p>
        <Link className="text-insight underline" href="/review/gold">
          العودة إلى قائمة الصفحات
        </Link>
      </main>
    );
  if (!d) return <main className="mx-auto max-w-3xl px-4 py-10">جارٍ التحميل…</main>;

  const p = d.progress;
  const done = p.items_done + p.spot_done;
  const all = p.items_total + p.spot_total;

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/review/gold" className="text-sm text-insight underline">
            كل الصفحات
          </Link>
          <h1 className="text-2xl font-semibold">صفحة {toArabicDigits(d.printed)}</h1>
        </div>
        <nav className="flex gap-2 text-sm" aria-label="مراحل المراجعة">
          {(
            [
              ["items", `مواضع الخلاف ${toArabicDigits(p.items_done)}/${toArabicDigits(p.items_total)}`],
              ["spot", `عيّنة التحقق ${toArabicDigits(p.spot_done)}/${toArabicDigits(p.spot_total)}`],
              ["structure", "البنية والاعتماد"],
            ] as [Mode, string][]
          ).map(([m, label]) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                setIdx(0);
              }}
              aria-pressed={mode === m}
              className={`rounded px-3 py-1.5 ${mode === m ? "bg-ink text-paper" : "border border-ink/20"}`}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      <div
        className="mt-4 h-2 w-full overflow-hidden rounded bg-ink/10"
        role="progressbar"
        aria-valuenow={done}
        aria-valuemax={all}
        aria-label="التقدم"
      >
        <div className="h-full bg-thread transition-all" style={{ width: `${all ? (100 * done) / all : 0}%` }} />
      </div>

      {mode === "items" && item && (
        <section className="mt-6" aria-live="polite">
          <p className="text-sm opacity-70">
            الموضع {toArabicDigits(idx + 1)} من {toArabicDigits(d.review_items.length)} ·{" "}
            {BLOCK_TYPES[d.blocks[item.block]?.type] ?? ""}
            {item.decision !== null && <span className="text-thread"> · تمت مراجعته</span>}
            {item.requeued && item.decision === null && (
              <span className="text-amber">
                {" "}
                · أعيد للمراجعة لأن الصورة السابقة لم تكن تعرض الموضع (اختيارك السابق: «
                {item.previous_decision}»)
              </span>
            )}
          </p>
          <Crop key={item.id} pid={d.page_id} x={item} />
          {context && (
            <p className="mt-3 font-source text-xl leading-loose">
              <span className="opacity-50">{context.before} </span>
              <mark className="rounded bg-thread/25 px-1">{item.candidates[0]?.text}</mark>
              <span className="opacity-50"> {context.after}</span>
            </p>
          )}
          <ol className="mt-4 grid gap-2">
            {item.candidates.map((c, i) => (
              <li key={c.text}>
                <button
                  onClick={() => decide(c.text)}
                  className={`flex w-full items-center justify-between gap-4 rounded-lg border px-4 py-3 text-start hover:border-insight ${
                    item.decision === c.text ? "border-thread bg-thread/10" : "border-ink/20"
                  }`}
                >
                  <span className="flex items-center gap-3">
                    <kbd className="rounded border border-ink/30 px-2 text-sm">{toArabicDigits(i + 1)}</kbd>
                    <span className="font-source text-2xl">{c.text}</span>
                  </span>
                  <span className="text-xs opacity-70">
                    {c.readers.length > 1
                      ? `${toArabicDigits(c.readers.length)} قراءات متطابقة`
                      : "قراءة واحدة"}
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <EditBox
            ref={editRef}
            value={edit}
            onChange={setEdit}
            onSave={() => decide(edit)}
            saveLabel="حفظ النص المعدّل"
          />
          <p className="mt-3 text-xs opacity-70">
            الاختصارات: ١–٣ اختيار · E تعديل · Enter حفظ · D حذف المقطع · ← التالي · → السابق
          </p>
        </section>
      )}

      {mode === "spot" && spot && (
        <section className="mt-6" aria-live="polite">
          <p className="text-sm opacity-70">
            عيّنة عشوائية من الكلمات المقبولة تلقائيًا ({toArabicDigits(idx + 1)} من{" "}
            {toArabicDigits(d.spotcheck.length)}). هل الكلمة مطابقة للمطبوع، بما في ذلك
            التشكيل؟
          </p>
          <Crop key={spot.id} pid={d.page_id} x={spot} />
          <p className="mt-4 font-source text-4xl">{spot.text}</p>
          <div className="mt-4 flex gap-3">
            <button className="rounded bg-thread px-4 py-2 text-ink" onClick={() => judge("ok")}>
              مطابقة (Y)
            </button>
            <button
              className="rounded border border-madder px-4 py-2 text-madder"
              onClick={() => editRef.current?.focus()}
            >
              غير مطابقة: صحّحها (N)
            </button>
          </div>
          <EditBox
            ref={editRef}
            value={edit}
            onChange={setEdit}
            onSave={() =>
              edit.trim() === spot.text ? judge("ok") : judge("wrong", edit.trim())
            }
            saveLabel="حفظ التصحيح"
          />
        </section>
      )}

      {mode === "items" && !item && <Done label="انتهت مواضع الخلاف في هذه الصفحة." />}
      {mode === "spot" && !spot && <Done label="انتهت عيّنة التحقق في هذه الصفحة." />}

      {mode === "structure" && <Structure d={d} page={page} reviewer={reviewer} onProgress={applyProgress} setD={setD} />}
    </main>
  );
}

function Crop({ pid, x }: { pid: string; x: Located }) {
  // Keyed by item id: a new dispute always mounts a new image, so the previous crop can never
  // stay on screen while the next one loads.
  const crop = cropUrl(pid, x);
  const [full, setFull] = useState(crop === null);
  const [loaded, setLoaded] = useState(false);
  const src = full ? pageUrl(pid, x) : crop!;
  const label =
    x.loc === "uncertain"
      ? "الموقع غير مؤكد: المنطقة المرجّحة مظللة بالكهرماني"
      : x.loc === "word"
        ? "الكلمات المختلف فيها مظللة باللون البنفسجي"
        : "الموقع تقريبي: الكلمات المرجّحة مظللة باللون البنفسجي";
  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className={x.loc === "word" ? "" : "font-medium text-amber"}>
          {x.loc === "word" ? "" : "⚠ "}
          {label}
        </span>
        {crop !== null && (
          <button
            className="rounded border border-ink/30 px-3 py-1"
            onClick={() => {
              setLoaded(false);
              setFull((f) => !f);
            }}
          >
            {full ? "عرض السطر فقط" : "عرض الصفحة كاملة"}
          </button>
        )}
      </div>
      <div className="relative mt-2 min-h-24 rounded border border-ink/15 bg-white">
        {!loaded && (
          <p className="absolute inset-0 grid place-items-center text-sm opacity-60">
            جارٍ تحميل الصورة…
          </p>
        )}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={src}
          src={src}
          onLoad={() => setLoaded(true)}
          alt={
            full
              ? "الصفحة الأصلية كاملة مع تظليل موضع الخلاف"
              : "السطر من الصفحة الأصلية مع تظليل الكلمات المختلف فيها"
          }
          className={`w-full rounded ${loaded ? "" : "invisible"}`}
        />
      </div>
    </div>
  );
}

function EditBox({
  ref,
  value,
  onChange,
  onSave,
  saveLabel,
}: {
  ref: React.RefObject<HTMLInputElement | null>;
  value: string;
  onChange: (v: string) => void;
  onSave: () => void;
  saveLabel: string;
}) {
  return (
    <div className="mt-4 flex flex-wrap gap-2">
      <label className="sr-only" htmlFor="edit">
        تعديل النص
      </label>
      <input
        id="edit"
        ref={ref}
        className="min-w-0 flex-1 rounded border border-ink/25 bg-background px-3 py-2 font-source text-2xl"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <button className="rounded border border-ink/30 px-4 py-2" onClick={onSave}>
        {saveLabel}
      </button>
    </div>
  );
}

function Done({ label }: { label: string }) {
  return <p className="mt-8 rounded-lg border border-thread/40 bg-thread/10 p-4">{label}</p>;
}

function Structure({
  d,
  page,
  reviewer,
  onProgress,
  setD,
}: {
  d: Draft;
  page: string;
  reviewer: string;
  onProgress: (p: Progress) => void;
  setD: React.Dispatch<React.SetStateAction<Draft | null>>;
}) {
  const [msg, setMsg] = useState("");
  const pending = d.progress.items_total - d.progress.items_done;
  return (
    <section className="mt-6">
      <p className="opacity-80">
        راجع نوع كل كتلة. الكتل التي اختلف فيها القارئان ملوّنة بالكهرماني. تعليق المحقق
        (مصطفى محمد عمارة) يُفصل عن متن الإمام النووي.
      </p>
      <ul className="mt-4 grid gap-2">
        {d.blocks.map((b) => {
          const current = b.type_confirmed ?? b.type;
          const disputed = b.type_reader_c !== null && b.type_reader_c !== b.type;
          return (
            <li
              key={b.order}
              className={`rounded-lg border p-3 ${disputed ? "border-amber bg-amber/10" : "border-ink/15"}`}
            >
              <div className="flex flex-wrap items-center gap-3">
                <select
                  aria-label={`نوع الكتلة ${b.order}`}
                  className="rounded border border-ink/25 bg-background px-2 py-1"
                  value={current}
                  onChange={async (e) => {
                    const type = e.target.value;
                    const p = await api<Progress>(`/${page}/block/${b.order}`, { type, reviewer });
                    setD((x) =>
                      x
                        ? {
                            ...x,
                            blocks: x.blocks.map((y) =>
                              y.order === b.order ? { ...y, type_confirmed: type } : y,
                            ),
                          }
                        : x,
                    );
                    onProgress(p);
                  }}
                >
                  {Object.entries(BLOCK_TYPES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                {disputed && (
                  <span className="text-xs">
                    ⚠ القارئ الآخر رآها: {BLOCK_TYPES[b.type_reader_c!] ?? b.type_reader_c}
                  </span>
                )}
                {b.footnote_marker && <span className="text-xs opacity-70">علامة {b.footnote_marker}</span>}
              </div>
              <p className="mt-2 line-clamp-2 font-source text-lg leading-loose">{b.text}</p>
            </li>
          );
        })}
      </ul>
      <div className="mt-6 flex items-center gap-4">
        <button
          disabled={pending > 0}
          className="rounded bg-ink px-5 py-2.5 text-paper disabled:opacity-40"
          onClick={async () => {
            try {
              const p = await api<Progress>(`/${page}/finalize`, { reviewer });
              onProgress(p);
              setMsg("اعتُمدت الصفحة وحُفظت في مجموعة المرجع.");
            } catch (e) {
              setMsg((e as Error).message);
            }
          }}
        >
          اعتماد الصفحة
        </button>
        {pending > 0 && <span className="text-sm">مواضع الخلاف المتبقية قبل الاعتماد: {toArabicDigits(pending)}.</span>}
        {msg && <span role="status">{msg}</span>}
      </div>
    </section>
  );
}
