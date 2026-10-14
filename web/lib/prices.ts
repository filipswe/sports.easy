import { api } from "./api";

type Refresh = { status: string; fetched_matches: number };
const requests = new Map<string, Promise<Refresh>>();
export function refreshPrices(body: {
  fixture_id?: string;
  period?: string;
  team?: string;
  league?: string;
  more?: boolean;
}) {
  const key = JSON.stringify(body);
  const existing = requests.get(key);
  if (existing) return existing;
  const request = (async () => {
    let result: Refresh = { status: "busy", fetched_matches: 0 };
    for (let attempt = 0; attempt < 4; attempt++) {
      result = await api<Refresh>("/prices/refresh", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (result.status !== "busy") break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    return result;
  })().finally(() => requests.delete(key));
  requests.set(key, request);
  return request;
}
