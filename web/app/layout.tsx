import type { Metadata } from "next";
import { ParlayProvider } from "@/components/parlay-context";
import { Shell } from "@/components/shell";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "sports.easy — Betting made easy",
    template: "%s | sports.easy",
  },
  description:
    "Research football matches with transparent statistical estimates, bookmaker comparisons and honest data quality.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <ParlayProvider>
          <Shell>{children}</Shell>
        </ParlayProvider>
      </body>
    </html>
  );
}
