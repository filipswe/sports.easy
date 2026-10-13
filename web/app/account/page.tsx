import { Suspense } from "react";
import { Account } from "@/components/account";
export const metadata = { title: "Your account" };
export default function Page() {
  return (
    <Suspense fallback={<p className="container section">Loading account…</p>}>
      <Account />
    </Suspense>
  );
}
