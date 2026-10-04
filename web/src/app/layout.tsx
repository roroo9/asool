import type { Metadata, Viewport } from "next";
import { Amiri, Amiri_Quran, IBM_Plex_Sans_Arabic } from "next/font/google";
import { SiteFooter, SiteHeader } from "@/components/Chrome";
import { LangProvider } from "@/lib/i18n";
import "./globals.css";

const plex = IBM_Plex_Sans_Arabic({
  variable: "--font-ui",
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600"],
});
const amiri = Amiri({ variable: "--font-source", subsets: ["arabic"], weight: ["400", "700"] });
const amiriQuran = Amiri_Quran({ variable: "--font-quran", subsets: ["arabic"], weight: "400" });

export const metadata: Metadata = {
  title: "أصول | Asool",
  description:
    "أداة بحث مدعومة بالذكاء الاصطناعي، كل نتيجة مرتبطة بموضعها في الصفحة الأصلية من الكتاب المطبوع",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f3ec" },
    { media: "(prefers-color-scheme: dark)", color: "#11163a" },
  ],
};

// Applies the saved theme and language before first paint (no flash).
const bootScript = `try{var t=localStorage.getItem('asool.theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t;var l=localStorage.getItem('asool.lang');if(l==='en'){document.documentElement.lang='en';document.documentElement.dir='ltr'}}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ar"
      dir="rtl"
      suppressHydrationWarning
      className={`${plex.variable} ${amiri.variable} ${amiriQuran.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: bootScript }} />
      </head>
      <body className="flex min-h-full flex-col">
        <LangProvider>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:p-2"
          >
            تخطَّ إلى المحتوى
          </a>
          <SiteHeader />
          <div id="main" className="flex flex-1 flex-col">
            {children}
          </div>
          <SiteFooter />
        </LangProvider>
      </body>
    </html>
  );
}
