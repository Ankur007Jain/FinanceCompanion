import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinanceCompanion",
  description: "AI-powered stock advisor for busy professionals",
  viewport: "width=device-width, initial-scale=1",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
