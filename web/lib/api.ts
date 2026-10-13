export type Selection = {
  id: string;
  fixture_id: string;
  home: string;
  away: string;
  competition: string;
  competition_id: string;
  kickoff: string;
  status: string;
  market: string;
  outcome: string;
  odds: number;
  bookmaker: string;
  bookmaker_id: string;
  region: string;
  probability: number;
  likelihood: string;
  failure_probability: number;
  estimated_ev: number;
  implied_probability: number;
  fair_odds: number;
  quality: string;
  stale: boolean;
  source_updated_at: string | null;
  fetched_at: string;
  generated_at: string;
  input_cutoff: string;
  model_version: string;
  mode: string;
  quote_basis: string;
  reason: string;
  result?: string;
  corrected?: boolean;
};
export type Meta = {
  mode: string;
  model_version: string;
  data_fetched_at: string | null;
  leagues: { id: string; name: string; season: number }[];
  bookmakers: { id: string; name: string; region: string }[];
  markets: string[];
  region: string;
  freshness_seconds: number;
  regional_notice: string;
  email_demo: boolean;
};
export type User = {
  id: string;
  email: string;
  admin: boolean;
  preferences: {
    timezone?: string;
    odds_format?: string;
    leagues?: string[];
    filters?: string;
  };
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && !["GET", "HEAD"].includes(options.method)) {
    const tokenResponse = await fetch("/api/auth/csrf", {
      credentials: "same-origin",
    });
    if (!tokenResponse.ok)
      throw new ApiError(
        "Unable to verify this request. Try again.",
        tokenResponse.status,
      );
    const token = await tokenResponse.json();
    headers.set("x-csrf-token", token.csrf);
  }
  const res = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (res.status === 204) return undefined as T;
  const json = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new ApiError(
      json.error?.message || "Service unavailable. Please try again.",
      res.status,
    );
  return json as T;
}
export const pct = (n: number) => (n * 100).toFixed(1) + "%";
export const marketName = (m: string) =>
  ({
    "1x2": "Match result",
    totals: "Total goals · 2.5",
    btts: "Both teams to score",
  })[m] || m;
export const selectionName = (s: Selection) =>
  ({
    home: s.home,
    away: s.away,
    draw: "Draw",
    over: "Over 2.5 goals",
    under: "Under 2.5 goals",
    yes: "Both teams score",
    no: "Both teams don’t score",
  })[s.outcome] || s.outcome;
export const stamp = (s: string | null, zone?: string) =>
  s
    ? new Date(s).toLocaleString("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: zone,
      })
    : "Not available";
export const initials = (name: string) =>
  name
    .split(" ")
    .map((s) => s[0])
    .slice(0, 3)
    .join("");
