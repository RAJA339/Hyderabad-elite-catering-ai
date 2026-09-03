import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: { default: "Hyderabad Elite Catering", template: "%s · HEC" },
  description: "WhatsApp-first catering with live Hyderabad market pricing, festival offers, and a personal AI consultant.",
  icons: { icon: "/favicon.svg" },
};
export const viewport: Viewport = { themeColor: [{ media: "(prefers-color-scheme: light)", color: "#fafaf9" }, { media: "(prefers-color-scheme: dark)", color: "#0b0b0c" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-dvh font-sans"><Providers>{children}</Providers></body>
    </html>
  );
}
