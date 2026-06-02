import type { Metadata, Viewport } from "next";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import { Providers } from "@/components/layout/Providers";
import "@/styles/globals.css";

// ── Fonts ──────────────────────────────────────────────────────
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-ui",
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-data",
  weight: ["400", "500", "700"],
  display: "swap",
});

// ── Metadata ───────────────────────────────────────────────────
export const metadata: Metadata = {
  title: {
    default: "BizVision AI — SME Decision Intelligence",
    template: "%s | BizVision AI",
  },
  description:
    "Elite AI-powered decision intelligence for SMEs. Recruitment, Pricing, Forecasting, ESG, and Financial Advisory in one cinematic platform.",
  keywords: [
    "AI business intelligence",
    "SME AI platform",
    "recruitment AI",
    "pricing optimization",
    "profit forecasting",
    "ESG scoring",
    "explainable AI",
  ],
  authors: [{ name: "BizVision AI Team" }],
  creator: "BizVision AI",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://bizvision-ai.com",
    title: "BizVision AI — SME Decision Intelligence",
    description: "Elite AI-powered decision intelligence for SMEs.",
    siteName: "BizVision AI",
  },
  twitter: {
    card: "summary_large_image",
    title: "BizVision AI",
    description: "Elite AI-powered decision intelligence for SMEs.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#050A14",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

// ── Root Layout ────────────────────────────────────────────────
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${jetbrainsMono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="bg-void text-text-primary antialiased overflow-x-hidden">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
