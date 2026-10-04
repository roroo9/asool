import type { Metadata } from "next";
import { Amiri, IBM_Plex_Sans_Arabic } from "next/font/google";
import "./globals.css";

const plex = IBM_Plex_Sans_Arabic({
  variable: "--font-ui",
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600"],
});

const amiri = Amiri({
  variable: "--font-source",
  subsets: ["arabic"],
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "أصول",
  description:
    "أداة بحث مدعومة بالذكاء الاصطناعي، كل نتيجة مرتبطة بموضعها في الصفحة الأصلية",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${plex.variable} ${amiri.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
