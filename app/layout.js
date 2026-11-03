import { Anton, Inter } from "next/font/google";
import "./globals.css";
import { site } from "@/data/site";

const anton = Anton({ weight: "400", subsets: ["latin"], variable: "--font-anton", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata = {
  metadataBase: new URL(site.url),
  title: site.seo.title,
  description: site.seo.description,
  openGraph: {
    title: site.seo.title,
    description: site.seo.description,
    url: site.url,
    siteName: site.name,
    images: [{ url: site.hero.photo, alt: site.hero.photoAlt }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: site.seo.title,
    description: site.seo.description,
    images: [site.hero.photo],
  },
};

export const viewport = {
  themeColor: "#121418",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${anton.variable} ${inter.variable}`}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
