import type { Metadata } from "next";
import { ParlayProvider } from "@/components/parlay-context";
import { Shell } from "@/components/shell";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "sports.easy — Betting made easy",
    template: "%s | sports.easy",
  },
  other: { "darkreader-lock": "true" },
  description:
    "Football picks, current sportsbook prices and clear match analysis.",
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
