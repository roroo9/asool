"use client";

import { forwardRef, useImperativeHandle, useMemo, useRef, useState } from "react";
import { TransformComponent, TransformWrapper, type ReactZoomPanPinchRef } from "react-zoom-pan-pinch";
import { ar, imageUrl } from "@/lib/api";
import type { Block, FootnoteLink, PageData, Rect } from "@/lib/types";

export const TYPE_COLORS: Record<string, string> = {
  body: "#3b6fd8",
  hadith: "#b13cb8",
  quran: "#1d9a5b",
  footnote: "#e08a10",
  editor_commentary: "#8b5a2b",
  heading: "#d33b3b",
  poetry: "#0f9a9a",
  page_number: "#888888",
  marginalia: "#888888",
  other: "#888888",
};

export const TYPE_LABELS: Record<string, string> = {
  body: "متن",
  hadith: "نص الحديث",
  quran: "آية",
  footnote: "حاشية",
  editor_commentary: "تعليق المحقق",
  heading: "عنوان",
  poetry: "شعر",
  page_number: "رقم الصفحة",
  marginalia: "هامش",
  other: "أخرى",
};

export type PageViewerHandle = {
  focusBlocks: (ids: string[]) => void;
  reset: () => void;
  /** DOM element covering the highlighted region (end point of the Source Thread). */
  highlightEl: () => HTMLElement | null;
};

type Props = {
  page: PageData;
  highlight?: string[];
  xray?: boolean;
  onBlockClick?: (b: Block) => void;
  className?: string;
};

const union = (rs: Rect[]): Rect => [
  Math.min(...rs.map((r) => r[0])),
  Math.min(...rs.map((r) => r[1])),
  Math.max(...rs.map((r) => r[2])),
  Math.max(...rs.map((r) => r[3])),
];

/** Approximate pixel position of a footnote marker inside its anchor block (RTL lines). */
function markerPoint(anchor: Block, link: FootnoteLink): [number, number] | null {
  const rects = anchor.rects?.length ? anchor.rects : anchor.bbox ? [anchor.bbox] : [];
  if (!rects.length) return null;
  const frac = link.anchor_char_offset != null ? link.anchor_char_offset / Math.max(1, anchor.text.length) : 0.5;
  const widths = rects.map((r) => r[2] - r[0]);
  const total = widths.reduce((a, b) => a + b, 0);
  let target = frac * total;
  for (let i = 0; i < rects.length; i++) {
    if (target <= widths[i] || i === rects.length - 1) {
      const r = rects[i];
      return [r[2] - Math.min(target, widths[i]), (r[1] + r[3]) / 2];
    }
    target -= widths[i];
  }
  return null;
}

export const PageViewer = forwardRef<PageViewerHandle, Props>(function PageViewer(
  { page, highlight = [], xray = false, onBlockClick, className = "" },
  ref,
) {
  const tf = useRef<ReactZoomPanPinchRef>(null);
  const hlRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<string | null>(null);
  const W = page.width;
  const H = page.height;
  const byId = useMemo(() => Object.fromEntries(page.blocks.map((b) => [b.id, b])), [page.blocks]);
  const hlBlocks = highlight.map((id) => byId[id]).filter((b): b is Block => !!b?.bbox);
  const hlBox = hlBlocks.length ? union(hlBlocks.map((b) => b.bbox as Rect)) : null;

  useImperativeHandle(ref, () => ({
    focusBlocks: () => {
      // zoom onto the highlight anchor (rendered for the current highlight)
      requestAnimationFrame(() => {
        if (hlRef.current) tf.current?.zoomToElement(hlRef.current, 1.8, 450);
      });
    },
    reset: () => tf.current?.resetTransform(300),
    highlightEl: () => hlRef.current,
  }));

  const pct = (r: Rect) => ({
    left: `${(r[0] / W) * 100}%`,
    top: `${(r[1] / H) * 100}%`,
    width: `${((r[2] - r[0]) / W) * 100}%`,
    height: `${((r[3] - r[1]) / H) * 100}%`,
  });

  const arcs = xray
    ? page.footnote_links
        .map((ln) => {
          const a = ln.anchor_block_id ? byId[ln.anchor_block_id] : null;
          const f = byId[ln.footnote_block_id];
          if (!a || !f?.bbox) return null;
          const p = markerPoint(a, ln);
          if (!p) return null;
          const q: [number, number] = [(f.bbox[0] + f.bbox[2]) / 2, f.bbox[1]];
          const mx = (p[0] + q[0]) / 2 + (p[1] < q[1] ? 120 : -120);
          const my = (p[1] + q[1]) / 2;
          return { id: `${ln.anchor_block_id}-${ln.footnote_block_id}`, d: `M ${p[0]} ${p[1]} Q ${mx} ${my} ${q[0]} ${q[1]}`, p };
        })
        .filter((x): x is { id: string; d: string; p: [number, number] } => !!x)
    : [];

  return (
    <div className={`relative overflow-hidden rounded-lg border border-line bg-white ${className}`}>
      <TransformWrapper ref={tf} minScale={1} maxScale={5} limitToBounds centerOnInit wheel={{ step: 0.15 }} doubleClick={{ mode: "zoomIn" }}>
        <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width: "100%" }}>
          <div className="relative w-full" style={{ aspectRatio: `${W} / ${H}` }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl(page.id)}
              alt={`صفحة ${ar(page.printed)} من كتاب رياض الصالحين، الطبعة الأصلية ١٩٥٦`}
              className="absolute inset-0 h-full w-full select-none"
              draggable={false}
            />
            <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full" aria-hidden={!xray} role={xray ? "img" : undefined} aria-label={xray ? "بنية الصفحة: الكتل وأنواعها وروابط الحواشي" : undefined}>
              {xray &&
                page.blocks.map((b, i) =>
                  (b.rects?.length ? b.rects : b.bbox ? [b.bbox] : []).map((r, k) => (
                    <rect
                      key={`${b.id}-${k}`}
                      x={r[0]}
                      y={r[1]}
                      width={r[2] - r[0]}
                      height={r[3] - r[1]}
                      fill={TYPE_COLORS[b.type] ?? "#888"}
                      fillOpacity={hover === b.id ? 0.22 : 0.1}
                      stroke={TYPE_COLORS[b.type] ?? "#888"}
                      strokeWidth={b.bbox_source === "fusion" ? 5 : 3}
                      strokeDasharray={b.bbox_source === "fusion" ? undefined : "14 8"}
                      onMouseEnter={() => setHover(b.id)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => onBlockClick?.(b)}
                      style={{ cursor: onBlockClick ? "pointer" : undefined }}
                    >
                      <title>{`${i + 1}. ${TYPE_LABELS[b.type] ?? b.type}`}</title>
                    </rect>
                  )),
                )}
              {xray &&
                arcs.map((a) => (
                  <g key={a.id}>
                    <path d={a.d} fill="none" stroke="#6c5ce7" strokeWidth={5} strokeOpacity={0.75} />
                    <circle cx={a.p[0]} cy={a.p[1]} r={12} fill="#6c5ce7" />
                  </g>
                ))}
              {xray &&
                hover &&
                byId[hover]?.bbox && (
                  <text
                    x={(byId[hover].bbox as Rect)[2] + 8}
                    y={(byId[hover].bbox as Rect)[1] + 40}
                    fontSize={48}
                    fill={TYPE_COLORS[byId[hover].type]}
                    fontWeight={700}
                  >
                    {ar(page.blocks.findIndex((b) => b.id === hover) + 1)}
                  </text>
                )}
              {hlBlocks.map((b) =>
                (b.rects?.length ? b.rects : [b.bbox as Rect]).map((r, k) => (
                  <rect
                    key={`hl-${b.id}-${k}`}
                    x={r[0] - 8}
                    y={r[1] - 6}
                    width={r[2] - r[0] + 16}
                    height={r[3] - r[1] + 12}
                    rx={10}
                    fill="#2fd4b5"
                    fillOpacity={0.22}
                    stroke="#0f8f78"
                    strokeWidth={6}
                  />
                )),
              )}
            </svg>
            {hlBox && <div ref={hlRef} data-highlight className="pointer-events-none absolute" style={pct(hlBox)} />}
          </div>
        </TransformComponent>
      </TransformWrapper>
    </div>
  );
});
