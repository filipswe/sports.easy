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
import { refreshPrices } from "@/lib/prices";
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
      : short && (pick.market.startsWith("totals") || pick.market === "btts")
        ? ({ over: "Over", under: "Under", yes: "Yes", no: "No" }[
            pick.outcome
          ] || pick.outcome) +
          (pick.market.startsWith("totals")
            ? ` ${pick.market === "totals" ? "2.5" : pick.market.split("_")[1]}`
            : "")
        : pickLabel(pick);
  return (
    <button
      className={`outcome ${selected ? "is-selected" : ""}`}
      onClick={() => toggle(pick)}
      aria-pressed={selected}
      aria-label={`${pickLabel(pick)}${pick.probability !== null ? `, ${pct(pick.probability)} estimated chance` : ""}${pick.odds ? `, odds ${pick.odds.toFixed(2)}` : ""}`}
    >
      <span>
        {selected && <Check size={12} />} {label}
      </span>
      <b>{pick.odds?.toFixed(2) || "—"}</b>
      {pick.probability !== null && <small>{pct(pick.probability)}</small>}
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
    goalLine = params.get("line") || "all",
    halfLine = params.get("half_line") || "all",
    league = params.get("league") || "";
  const [input, setInput] = useState(search),
    [matches, setMatches] = useState<MatchRow[] | null>(null),
    [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const selectedMarket = market.startsWith("half_totals")
    ? `half_totals_${halfLine}`
    : market === "totals" && goalLine !== "2.5"
      ? `totals_${goalLine}`
      : market;
  const [loadingMore, setLoadingMore] = useState(false);
  async function loadMore() {
    setLoadingMore(true);
    try {
      await refreshPrices({ period, team: search, league, more: true });
      const result = await api<{ items: MatchRow[] }>(
        "/matchday?" +
          new URLSearchParams({
            period,
            team: search,
            league,
            market: selectedMarket,
          }),
      );
      setMatches(result.items);
      setError("");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to load prices. Try again.",
      );
    } finally {
      setLoadingMore(false);
    }
  }
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
    const load = async (refresh = true) => {
      if (refresh && meta?.mode === "live" && market !== "1x2") {
        await refreshPrices({ period, team: search, league });
      }
      return api<{ items: MatchRow[] }>(
        "/matchday?" +
          new URLSearchParams({
            period,
            team: search,
            league,
            market: selectedMarket,
          }),
      );
    };
    const fetchMatches = (refresh: boolean) =>
      load(refresh)
        .then((r) => {
          if (active) {
            setMatches(r.items);
            setError("");
          }
        })
        .catch((e) => {
          if (active)
            setError(
              e instanceof TypeError
                ? "Connection interrupted. Please try again."
                : e.message,
            );
        });
    fetchMatches(true);
    const interval = window.setInterval(() => {
      if (!document.hidden) fetchMatches(false);
    }, 60000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [period, search, league, market, selectedMarket, meta?.mode, retry]);
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
                ["fortnight", "Next 14 days"],
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
              ["totals", "Under/over goals"],
              ["half_totals_0.5", "First-half goals"],
              ["double_chance", "Double chance"],
            ].map(([v, l]) => (
              <button
                className={
                  market === v ||
                  (v.startsWith("half_totals") &&
                    market.startsWith("half_totals"))
                    ? "active"
                    : ""
                }
                key={v}
                onClick={() => update("market", v)}
              >
                {l}
              </button>
            ))}
          </div>
          {(market === "totals" || market.startsWith("half_totals")) && (
            <label className="goal-line-control">
              Goal line
              <select
                value={market === "totals" ? goalLine : halfLine}
                onChange={(e) =>
                  update(
                    market === "totals" ? "line" : "half_line",
                    e.target.value,
                  )
                }
              >
                <option value="all">All goal lines</option>
                {Array.from({ length: 10 }, (_, n) => `${n + 0.5}`).map(
                  (line) => (
                    <option key={line} value={line}>
                      {line} goals
                    </option>
                  ),
                )}
              </select>
            </label>
          )}
          <div className="list-caption">
            <span>
              {matches
                ? `${matches.length} upcoming matches`
                : "Loading matches…"}
            </span>
            <span>
              {meta?.mode === "demo" ? "Sample odds" : "Current odds"} ·
              Estimated chance %
            </span>
          </div>
          {error ? (
            <ErrorBox
              message={error}
              retry={() => setRetry((attempt) => attempt + 1)}
            />
          ) : !matches ? (
            <Skeletons />
          ) : !list.length ? (
            <Empty
              title={
                meta?.mode === "live" && market !== "1x2"
                  ? "No quoted matches for this market"
                  : "No matches found"
              }
            >
              <button
                className="text-button"
                onClick={() => router.replace("/predictions")}
              >
                Reset filters
              </button>{" "}
              or try another goal line, market or date.
            </Empty>
          ) : (
            <div className="match-list">
              {list.map((m, i) => {
                const groups = m.markets
                    .filter((g) =>
                      selectedMarket === "totals_all"
                        ? g.key === "totals" || g.key.startsWith("totals_")
                        : selectedMarket === "half_totals_all"
                          ? g.key.startsWith("half_totals_")
                          : g.key === selectedMarket,
                    )
                    .sort((a, b) =>
                      selectedMarket.endsWith("_all")
                        ? Number(
                            a.key === "totals"
                              ? "2.5"
                              : a.key.split("_").at(-1),
                          ) -
                          Number(
                            b.key === "totals"
                              ? "2.5"
                              : b.key.split("_").at(-1),
                          )
                        : 0,
                    ),
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
                      <div
                        className={`fixture-outcomes ${selectedMarket.endsWith("_all") ? "all-goal-lines" : ""}`}
                      >
                        {groups.length ? (
                          groups.map((group) => (
                            <div className="fixture-line" key={group.key}>
                              {group.picks.map((p) => (
                                <OutcomeButton
                                  key={p.outcome}
                                  pick={withMatch(p, m)}
                                  short
                                />
                              ))}
                            </div>
                          ))
                        ) : (
                          <span className="hint">
                            No sportsbook quote for this market
                          </span>
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
            Tap a team for form, stats and all markets.
          </p>
          {meta?.mode === "live" && market !== "1x2" && (
            <button
              className="button secondary"
              onClick={loadMore}
              disabled={!matches || loadingMore}
            >
              {loadingMore
                ? "Finding current prices…"
                : "Find more priced matches"}
            </button>
          )}
        </div>
        <ParlayPanel />
      </div>
    </div>
  );
}
