import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Multi-agent istraživač",
  description: "Planer, paralelni istraživači i sintetizator nad SEC EDGAR podacima, uživo",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sr">
      <body>{children}</body>
    </html>
  );
}
