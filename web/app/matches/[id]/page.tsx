import { MatchDetail } from "@/components/match";
export const metadata = { title: "Match analysis" };
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MatchDetail id={id} />;
}
