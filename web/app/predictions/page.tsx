import { Suspense } from "react";
import { MatchBrowser } from "@/components/match-browser";
import { Skeletons } from "@/components/ui";
export const metadata = { title: "All matches & predictions" };
export default function Page() {
  return (
    <Suspense fallback={<Skeletons />}>
      <MatchBrowser />
    </Suspense>
  );
}
