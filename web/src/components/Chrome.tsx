"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useLang, useT } from "@/lib/i18n";
import { BOOK_ID } from "@/lib/types";

type Theme = "system" | "light" | "dark";

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (t === "dark" || t === "light") setTheme(t);
  }, []);
  const cycle = () => {
    const next: Theme = theme === "system" ? "dark" : theme === "dark" ? "light" : "system";
    setTheme(next);
    try {
      if (next === "system") {
        localStorage.removeItem("asool.theme");
        delete document.documentElement.dataset.theme;
      } else {
        localStorage.setItem("asool.theme", next);
        document.documentElement.dataset.theme = next;
      }
    } catch {
      /* storage unavailable: theme applies for this page only */
      if (next !== "system") document.documentElement.dataset.theme = next;
    }
  };
  const label = theme === "dark" ? "☾" : theme === "light" ? "☀" : "◐";
  return (
    <button
      onClick={cycle}
      className="rounded-md border border-line px-2.5 py-1 text-sm"
      aria-label={`المظهر: ${theme === "system" ? "تلقائي" : theme === "dark" ? "داكن" : "فاتح"}`}
      title="المظهر"
    >
      {label}
    </button>
  );
}

export function SiteHeader() {
  const t = useT();
  const { lang, setLang } = useLang();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const links: [string, string][] = [
    ["/ask", t("nav_ask")],
    [`/b/${BOOK_ID}/p/41`, t("nav_book")],
    ["/compare", t("nav_compare")],
    ["/proof", t("nav_proof")],
    ["/review", t("nav_review")],
    ["/how", t("nav_how")],
    ["/developers", t("nav_dev")],
  ];
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2.5">
        <Link href="/" className="font-source text-2xl font-bold leading-none">
          {t("brand")}
        </Link>
        <nav aria-label="التنقل الرئيسي" className="hidden flex-1 gap-1 md:flex">
          {links.map(([href, label]) => {
            const active = path === href || (href !== "/" && path.startsWith(href.split("/p/")[0]));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-ink/10 font-medium" : "text-muted hover:text-foreground"}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="ms-auto flex items-center gap-2">
          <button
            onClick={() => setLang(lang === "ar" ? "en" : "ar")}
            className="rounded-md border border-line px-2.5 py-1 text-sm"
          >
            {t("lang_toggle")}
          </button>
          <ThemeToggle />
          <button
            className="rounded-md border border-line px-2.5 py-1 text-sm md:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((o) => !o)}
          >
            ☰
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" aria-label="التنقل" className="grid gap-1 border-t border-line px-4 py-2 md:hidden">
          {links.map(([href, label]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)} className="rounded-md px-2 py-2">
              {label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function SiteFooter() {
  const t = useT();
  return (
    <footer className="mt-12 border-t border-line">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 text-xs text-muted">
        <p>{t("honest")}</p>
        <p>
          رياض الصالحين، طبعة دار إحياء الكتب العربية ١٩٥٦ · نص القرآن: مجمع الملك فهد · لا تُجمع
          بيانات شخصية
        </p>
      </div>
    </footer>
  );
}
