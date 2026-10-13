"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Search,
  Clock3,
  ChevronRight,
  Check,
  CalendarDays,
} from "lucide-react";
import { api, pct } from "@/lib/api";
import { MatchRow, Pick, pickKey, pickLabel, withMatch } from "@/lib/matchday";
import { useParlay } from "./parlay-context";
import { useApp } from "./shell";
import { ParlayPanel } from "./parlay-panel";
import { Empty, ErrorBox, Skeletons, TeamBadge } from "./ui";
export function OutcomeButton({
  pick,
  short = false,
}: {
  pick: Pick;
  short?: boolean;
}) {
  const { picks, toggle } = useParlay(),
    selected = picks.some((p) => pickKey(p) === pickKey(pick));
  const label =
    short && pick.market === "1x2"
      ? { home: "1", draw: "X", away: "2" }[pick.outcome] || pick.outcome
      : short && ["totals", "btts"].includes(pick.market)
        ? { over: "Over", under: "Under", yes: "Yes", no: "No" }[
            pick.outcome
          ] || pick.outcome
        : pickLabel(pick);
  return (
    <button
      className={`outcome ${selected ? "is-selected" : ""}`}
      onClick={() => toggle(pick)}
      aria-pressed={selected}
      aria-label={`${pickLabel(pick)}, ${pct(pick.probability)} model chance${pick.odds ? `, odds ${pick.odds.toFixed(2)}` : ""}`}
    >
      <span>
        {selected && <Check size={12} />} {label}
      </span>
      <b>{pick.odds?.toFixed(2) || "—"}</b>
      <small>{pct(pick.probability)}</small>
    </button>
  );
}
export function MatchBrowser() {
  const params = useSearchParams(),
    router = useRouter(),
    { meta } = useApp();
  const period = params.get("period") || "week",
    search = params.get("team") || "",
    market = params.get("market") || "1x2",
    league = params.get("league") || "";
  const [input, setInput] = useState(search),
    [matches, setMatches] = useState<MatchRow[] | null>(null),
    [error, setError] = useState("");
  function update(key: string, value: string) {
    const q = new URLSearchParams(params);
    if (value) q.set(key, value);
    else q.delete(key);
    router.replace("/predictions?" + q.toString(), { scroll: false });
  }
  useEffect(() => {
    setInput(search);
  }, [search]);
  useEffect(() => {
    let active = true;
    setError("");
    setMatches(null);
    api<{ items: MatchRow[] }>(
      "/matchday?" + new URLSearchParams({ period, team: search, league }),
    )
      .then((r) => {
        if (active) setMatches(r.items);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [period, search, league]);
  const list = matches
    ? [...matches].sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff))
    : [];
  return (
    <div className="container section app-page">
      <div className="page-heading">
        <div className="overline">THE MATCH CENTRE</div>
        <h1>Find your next pick.</h1>
        <p>
          Every match, a clearer picture. Choose an outcome to start your
          parlay.
        </p>
      </div>
      <div className="browse-layout">
        <div className="match-list-area">
          <div className="match-toolbar">
            <form
              className="search-field"
              onSubmit={(e) => {
                e.preventDefault();
                update("team", input);
              }}
            >
              <Search size={18} />
              <input
                aria-label="Search teams"
                placeholder="Search a team…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
              />
              <button type="submit" className="text-button">
                Search
              </button>
            </form>
            <label className="sr-only" htmlFor="league">
              League
            </label>
            <select
              id="league"
              value={league}
              onChange={(e) => update("league", e.target.value)}
            >
              <option value="">All leagues</option>
              {meta?.leagues.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>
          <div className="match-controls">
            <div className="segmented">
              {[
                ["today", "Today"],
                ["tomorrow", "Tomorrow"],
                ["week", "Next 7 days"],
              ].map(([v, l]) => (
                <button
                  key={v}
                  className={period === v ? "active" : ""}
                  onClick={() => update("period", v)}
                >
                  {l}
                </button>
              ))}
            </div>
            <span className="sort-select">
              <Clock3 size={15} />
              Kickoff order
            </span>
          </div>
          <div className="market-tabs" aria-label="Markets">
            {[
              ["1x2", "1X2"],
              ["btts", "BTTS"],
              ["totals", "Over/under 2.5"],
              ["half_totals_0.5", "First-half goals"],
              ["double_chance", "Double chance"],
            ].map(([v, l]) => (
              <button
                className={market === v ? "active" : ""}
                key={v}
                onClick={() => update("market", v)}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="list-caption">
            <span>
              {matches
                ? `${matches.length} upcoming matches`
                : "Loading matches…"}
            </span>
            <span>
              {meta?.mode === "demo" ? "Sample odds" : "Current odds"} · Model
              chance %
            </span>
          </div>
          {error ? (
            <ErrorBox message={error} />
          ) : !matches ? (
            <Skeletons />
          ) : !list.length ? (
            <Empty title="No matches found">
              <button
                className="text-button"
                onClick={() => router.replace("/predictions")}
              >
                Reset filters
              </button>{" "}
              or try another date.
            </Empty>
          ) : (
            <div className="match-list">
              {list.map((m, i) => {
                const group = m.markets.find((g) => g.key === market),
                  day = new Date(m.kickoff).toLocaleDateString("en-GB", {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                  });
                const previous = i
                  ? new Date(list[i - 1].kickoff).toDateString()
                  : "";
                return (
                  <div key={m.id}>
                    {new Date(m.kickoff).toDateString() !== previous && (
                      <div className="league-row">
                        <span>⚽ {m.competition}</span>
                        <span>
                          <CalendarDays size={13} />
                          {day}
                        </span>
                      </div>
                    )}
                    <article className="fixture-row" data-kickoff={m.kickoff}>
                      <div className="fixture-time">
                        {new Date(m.kickoff).toLocaleTimeString("en-GB", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                        <small>Upcoming</small>
                      </div>
                      <Link className="fixture-teams" href={"/matches/" + m.id}>
                        <span>
                          <TeamBadge name={m.home} src={m.home_logo} />
                          <strong>{m.home}</strong>
                        </span>
                        <span>
                          <TeamBadge name={m.away} src={m.away_logo} />
                          <strong>{m.away}</strong>
                        </span>
                      </Link>
                      <div className="fixture-outcomes">
                        {group?.picks.length ? (
                          group.picks.map((p) => (
                            <OutcomeButton
                              key={p.outcome}
                              pick={withMatch(p, m)}
                              short
                            />
                          ))
                        ) : (
                          <span className="hint">Awaiting match data</span>
                        )}
                      </div>
                      <Link
                        className="match-more"
                        href={"/matches/" + m.id}
                        aria-label={`Analysis for ${m.home} vs ${m.away}`}
                      >
                        <ChevronRight size={18} />
                      </Link>
                    </article>
                  </div>
                );
              })}
            </div>
          )}
          <p className="fine-print">
            {meta?.mode === "demo"
              ? "Sample odds from Demo Sportsbook."
              : "Prices from the connected sportsbook."}{" "}
            A dash means no price is available. Tap a team for form, stats and
            all markets.
          </p>
        </div>
        <ParlayPanel />
      </div>
    </div>
  );
}
