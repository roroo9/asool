"use client";

import { useEffect, useState } from "react";

/**
 * The Source Thread (CLAUDE.md §7.1): a fine luminous line from the cited sentence to the
 * highlighted lines on the original page image. Follows both elements while the page pans/zooms
 * (tracks for ~1s after each change). With reduced motion the line appears without animation.
 */
export function SourceThread({ from, to }: { from: HTMLElement | null; to: () => HTMLElement | null }) {
  const [d, setD] = useState<string | null>(null);
  const [len, setLen] = useState(2000);
  useEffect(() => {
    if (!from) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setD(null);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = () => {
      const target = to();
      if (target) {
        const a = from.getBoundingClientRect();
        const raw = target.getBoundingClientRect();
        // Clip the highlighted region to the visible part of the page pane.
        const pane = target.closest("[data-pageviewer]")?.getBoundingClientRect();
        const b = pane
          ? {
              left: Math.max(raw.left, pane.left),
              right: Math.min(raw.right, pane.right),
              top: Math.max(raw.top, pane.top),
              bottom: Math.min(raw.bottom, pane.bottom),
            }
          : raw;
        const visible = b.right > b.left && b.bottom > b.top && b.bottom > 0 && b.top < window.innerHeight;
        if (visible) {
          const rtl = document.documentElement.dir === "rtl";
          // start at the chip's inner edge (towards the page pane), end at the region's edge
          const x1 = rtl ? a.left : a.right;
          const y1 = a.top + a.height / 2;
          const x2 = rtl ? b.right : b.left;
          const y2 = (b.top + b.bottom) / 2;
          const mx = (x1 + x2) / 2;
          setD(`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`);
          setLen(Math.hypot(x2 - x1, y2 - y1) * 1.3 + 40);
        } else {
          setD(null);
        }
      }
      if (performance.now() - start < 1100) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    const onMove = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    };
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, [from, to]);
  if (!d) return null;
  return (
    <svg className="pointer-events-none fixed inset-0 z-30 hidden h-full w-full lg:block" aria-hidden>
      <path d={d} fill="none" stroke="#2fd4b5" strokeOpacity={0.25} strokeWidth={8} strokeLinecap="round" />
      <path
        key={d.slice(0, 12)}
        d={d}
        fill="none"
        stroke="#2fd4b5"
        strokeWidth={2}
        strokeLinecap="round"
        className="thread-path"
        style={{ ["--len" as string]: String(Math.round(len)) }}
      />
    </svg>
  );
}
