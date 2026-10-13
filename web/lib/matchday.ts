export type PickAnalysis = {
  summary: string;
  heading: string;
  model_favors: boolean;
  signals: { label: string; value: string }[];
  caution: string;
};
export type Price = {
  bookmaker: string;
  odds: number;
  stale: boolean;
  updated_at?: string;
};
export type Pick = {
  fixture_id: string;
  market: string;
  outcome: string;
  probability: number;
  analysis?: PickAnalysis;
  odds: number | null;
  bookmaker: string | null;
  stale: boolean;
  publication_id?: string | null;
  prices: Price[];
  home: string;
  away: string;
  home_logo?: string | null;
  away_logo?: string | null;
  kickoff: string;
  user_odds?: number | null;
};
export type Market = {
  key: string;
  name: string;
  group: string;
  picks: Pick[];
};
export type MatchRow = {
  id: string;
  home: string;
  away: string;
  home_logo?: string;
  away_logo?: string;
  competition: string;
  competition_id: string;
  kickoff: string;
  mode: string;
  status: string;
  markets: Market[];
};
export type Parlay = {
  legs: Pick[];
  probability: number;
  failure_probability: number;
  combined_odds: number | null;
  odds_basis: string;
  prices: Price[];
  approximation: string;
  mode: string;
};
export const pickKey = (p: Pick) =>
  [p.fixture_id, p.market, p.outcome].join(":");
export function pickLabel(p: {
  market: string;
  outcome: string;
  home: string;
  away: string;
}) {
  const o = p.outcome;
  if (p.market === "1x2")
    return o === "home"
      ? `${p.home} to win`
      : o === "away"
        ? `${p.away} to win`
        : "Draw";
  if (p.market === "btts")
    return o === "yes" ? "Both teams to score" : "Both teams to score: No";
  if (p.market === "double_chance")
    return o === "1x"
      ? `${p.home} or draw`
      : o === "x2"
        ? `${p.away} or draw`
        : "Either team to win";
  if (p.market === "correct_score")
    return o === "other" ? "Any other score" : `Correct score ${o}`;
  const line = p.market === "totals" ? "2.5" : p.market.split("_").at(-1);
  const prefix = p.market.startsWith("half_")
    ? "1st half: "
    : p.market.startsWith("home_")
      ? `${p.home}: `
      : p.market.startsWith("away_")
        ? `${p.away}: `
        : "";
  return `${prefix}${o === "over" ? "Over" : "Under"} ${line} goals`;
}
export const marketLabel = (market: string) =>
  market === "1x2"
    ? "Match result"
    : market === "btts"
      ? "Both teams to score"
      : market === "double_chance"
        ? "Double chance"
        : market === "correct_score"
          ? "Correct score"
          : market.startsWith("half_")
            ? "First-half goals"
            : market.includes("_goals_")
              ? "Team goals"
              : "Total goals";
export const withMatch = (p: Pick, m: MatchRow): Pick => ({
  ...p,
  home: m.home,
  away: m.away,
  home_logo: m.home_logo,
  away_logo: m.away_logo,
  kickoff: m.kickoff,
});
