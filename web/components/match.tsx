"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Sparkles, Bookmark, Check } from "lucide-react";
import { api, pct, stamp } from "@/lib/api";
import { MatchRow, Pick, pickLabel, withMatch } from "@/lib/matchday";
import { ErrorBox, TeamBadge, Skeletons } from "./ui";
import { ParlayPanel } from "./parlay-panel";
import { OutcomeButton } from "./match-browser";
import { useParlay } from "./parlay-context";
import { useApp } from "./shell";
type Stats = {
  recent: {
    opponent: string;
    score: string;
    result: string;
    kickoff: string;
  }[];
  home: { matches: number; scored: number; conceded: number };
  away: { matches: number; scored: number; conceded: number };
  rest_days: number | null;
};
type Detail = {
  id: string;
  home: string;
  away: string;
  venue: string | null;
  status: string;
  home_stats: Stats;
  away_stats: Stats;
  head_to_head: { home: string; away: string; score: string }[];
  prediction: {
    generated_at: string;
    input_cutoff: string;
    model_version: string;
    factors: {
      home_rate: number;
      away_rate: number;
      first_half: { home_rate: number; away_rate: number } | null;
    };
  } | null;
  explanation: { text: string };
};
function Form({ stats }: { stats: Stats }) {
  return (
    <div className="form-dots">
      {[...stats.recent].reverse().map((r, i) => (
        <span
          key={i}
          className={`form-dot ${r.result.toLowerCase()}`}
          title={`${r.opponent} · ${r.score}`}
        >
          {r.result}
        </span>
      ))}
    </div>
  );
}
function Recent({ name, stats }: { name: string; stats: Stats }) {
  return (
    <div className="panel recent-panel">
      <div className="section-heading">
        <h3>
          <TeamBadge name={name} />
          {name}
        </h3>
        <Form stats={stats} />
      </div>
      {stats.recent.length ? (
        stats.recent.map((r, i) => (
          <div className="recent-row" key={i}>
            <span className={`form-dot ${r.result.toLowerCase()}`}>
              {r.result}
            </span>
            <span>
              {new Date(r.kickoff).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
              })}
            </span>
            <span>
              <TeamBadge name={r.opponent} />
              {r.opponent}
            </span>
            <b>{r.score}</b>
          </div>
        ))
      ) : (
        <p>No recent results available.</p>
      )}
      <small>Newest first · Scores shown home–away</small>
    </div>
  );
}
export function MatchDetail({ id }: { id: string }) {
  const [match, setMatch] = useState<MatchRow | null>(null),
    [detail, setDetail] = useState<Detail | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("Markets"),
    [group, setGroup] = useState("Popular"),
    [focus, setFocus] = useState<Pick | null>(null),
    [saved, setSaved] = useState(false),
    [saveError, setSaveError] = useState("");
  const { picks } = useParlay(),
    { user } = useApp();
  useEffect(() => {
    let active = true;
    Promise.all([
      api<MatchRow>("/matchday/" + id),
      api<Detail>("/fixtures/" + id),
    ])
      .then(([m, d]) => {
        if (active) {
          setMatch(m);
          setDetail(d);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id]);
  useEffect(() => {
    const selected = picks.find((p) => p.fixture_id === id);
    if (selected) setFocus(selected);
    setSaved(false);
  }, [picks, id]);
  if (error)
    return (
      <div className="container section">
        <ErrorBox message={error} />
      </div>
    );
  if (!match || !detail)
    return (
      <div className="container section">
        <Skeletons />
      </div>
    );
  const candidate =
    [...match.markets.flatMap((m) => m.picks)]
      .sort((a, b) => b.probability - a.probability)
      .find((p) => p.market === "1x2") || match.markets[0]?.picks[0];
  const chosen = focus || (candidate ? withMatch(candidate, match) : null);
  const available = match.markets.filter(
    (m) =>
      group === "All" ||
      m.group === group ||
      (group === "Popular" && m.key === "totals"),
  );
  const h = detail.prediction?.factors.home_rate,
    a = detail.prediction?.factors.away_rate;
  const won = (s: Stats) => s.recent.filter((r) => r.result === "W").length;
  async function save() {
    if (!chosen?.publication_id) return;
    setSaveError("");
    try {
      await api("/saved", {
        method: "POST",
        body: JSON.stringify({ publication_id: chosen.publication_id }),
      });
      setSaved(true);
    } catch (e) {
      setSaveError((e as Error).message);
    }
  }
  return (
    <div className="container section app-page">
      <Link className="back-link" href="/predictions">
        <ArrowLeft size={15} />
        All matches
      </Link>
      <div className="match-hero">
        <div className="match-hero-top">
          <span>⚽ {match.competition}</span>
          <span>
            {stamp(match.kickoff)} · {detail.status}
          </span>
        </div>
        <div className="match-title">
          <div>
            <TeamBadge name={match.home} src={match.home_logo} />
            <h1>{match.home}</h1>
            <Form stats={detail.home_stats} />
          </div>
          <span className="versus">
            VS<small>PRE-MATCH</small>
          </span>
          <div>
            <TeamBadge name={match.away} src={match.away_logo} />
            <h1>{match.away}</h1>
            <Form stats={detail.away_stats} />
          </div>
        </div>
        {detail.venue && <p>{detail.venue}</p>}
      </div>
      <div className="browse-layout">
        <div className="match-list-area">
          <div className="tabs page-tabs">
            {["Markets", "Form & stats", "Head to head"].map((t) => (
              <button
                key={t}
                className={tab === t ? "active" : ""}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "Markets" ? (
            <>
              <div className="insight-card">
                <div className="overline">
                  <Sparkles size={15} />{" "}
                  {focus ? "YOUR PICK, ANALYZED" : "THE MODEL’S VIEW"}
                </div>
                <h2>
                  {chosen ? pickLabel(chosen) : "Awaiting enough match data"}
                </h2>
                {chosen && (
                  <>
                    <div className="insight-values">
                      <div>
                        <strong>{pct(chosen.probability)}</strong>
                        <span>Estimated chance</span>
                      </div>
                      <div>
                        <strong>{chosen.odds?.toFixed(2) || "—"}</strong>
                        <span>
                          {match.mode === "demo"
                            ? "Sample odds"
                            : "Recorded odds"}
                        </span>
                      </div>
                      <div>
                        <strong>{pct(1 - chosen.probability)}</strong>
                        <span>Chance it loses</span>
                      </div>
                    </div>
                    <p>
                      {match.home} won {won(detail.home_stats)} of their last{" "}
                      {detail.home_stats.recent.length}; {match.away} won{" "}
                      {won(detail.away_stats)} of their last{" "}
                      {detail.away_stats.recent.length}.
                      {h !== undefined && a !== undefined
                        ? ` The model expects about ${h.toFixed(1)} goals from ${match.home} and ${a.toFixed(1)} from ${match.away}.`
                        : ""}
                    </p>
                    <p className="hint">
                      {chosen.probability >= 0.7
                        ? "One of the more likely outcomes in this match, though an upset is still possible."
                        : chosen.probability >= 0.5
                          ? "The model gives this a slight edge. There is still a substantial chance it loses."
                          : "The model considers this less likely than not. Longer odds do not make it more likely to happen."}
                    </p>
                    {chosen.publication_id &&
                      (user ? (
                        <button
                          className="text-button"
                          disabled={saved}
                          onClick={save}
                        >
                          {saved ? <Check size={15} /> : <Bookmark size={15} />}{" "}
                          {saved ? "Pick saved" : "Save this pick"}
                        </button>
                      ) : (
                        <Link
                          className="text-link"
                          href={
                            "/account?next=" +
                            encodeURIComponent("/matches/" + id)
                          }
                        >
                          Sign in to save this pick →
                        </Link>
                      ))}
                  </>
                )}
                {saveError && <ErrorBox message={saveError} />}
              </div>
              <div className="market-tabs">
                {[
                  "Popular",
                  "Goals",
                  "First half",
                  "Team goals",
                  "Score",
                  "All",
                ].map((g) => (
                  <button
                    className={group === g ? "active" : ""}
                    key={g}
                    onClick={() => setGroup(g)}
                  >
                    {g}
                  </button>
                ))}
              </div>
              <div className="market-panels">
                {available.map((m) => (
                  <section className="panel market-panel" key={m.key}>
                    <div className="section-heading">
                      <h3>{m.name}</h3>
                      <span className="hint">Odds / model chance</span>
                    </div>
                    {m.picks.length ? (
                      <div
                        className={`market-options ${m.key === "correct_score" ? "score-options" : ""}`}
                      >
                        {m.picks.map((p) => (
                          <div
                            key={p.outcome}
                            onFocus={() => {
                              setFocus(withMatch(p, match));
                              setSaved(false);
                            }}
                          >
                            <OutcomeButton pick={withMatch(p, match)} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p>
                        Not enough first-half history to estimate this market
                        yet.
                      </p>
                    )}
                  </section>
                ))}
              </div>
              <p className="fine-print">
                {match.mode === "demo" ? "Sample data. " : ""}A dash means an
                odds quote is unavailable; you can still analyze the pick and
                enter your own price in the parlay builder.
              </p>
            </>
          ) : tab === "Form & stats" ? (
            <>
              <div className="stats-comparison panel">
                <h2>Match at a glance</h2>
                {[
                  ["Model goals", h?.toFixed(1) || "—", a?.toFixed(1) || "—"],
                  [
                    "Wins in last five",
                    won(detail.home_stats),
                    won(detail.away_stats),
                  ],
                  [
                    "Goals scored (last available home / away games)",
                    detail.home_stats.home.scored,
                    detail.away_stats.away.scored,
                  ],
                  [
                    "Goals conceded",
                    detail.home_stats.home.conceded,
                    detail.away_stats.away.conceded,
                  ],
                  [
                    "Matches in sample",
                    detail.home_stats.home.matches,
                    detail.away_stats.away.matches,
                  ],
                ].map(([label, x, y]) => (
                  <div className="comparison-stat" key={String(label)}>
                    <b>{x}</b>
                    <span>{label}</span>
                    <b>{y}</b>
                  </div>
                ))}
              </div>
              <Recent name={match.home} stats={detail.home_stats} />
              <Recent name={match.away} stats={detail.away_stats} />
            </>
          ) : (
            <section className="panel">
              <h2>Previous meetings</h2>
              {detail.head_to_head.length ? (
                detail.head_to_head.map((r, i) => (
                  <div className="h2h-row" key={i}>
                    <span>
                      <TeamBadge name={r.home} />
                      {r.home}
                    </span>
                    <b>{r.score}</b>
                    <span>
                      <TeamBadge name={r.away} />
                      {r.away}
                    </span>
                  </div>
                ))
              ) : (
                <p>No previous meetings in the available history.</p>
              )}
            </section>
          )}
          <details className="method-details">
            <summary>About these estimates & data</summary>
            <p>{detail.explanation.text}</p>
            <p>
              First-half estimates use a separate fit to recorded half-time
              scores. Injury and lineup information is not included.
            </p>
            <p>
              Model: {detail.prediction?.model_version || "Unavailable"} ·
              Updated {stamp(detail.prediction?.generated_at || null)}
            </p>
          </details>
        </div>
        <ParlayPanel />
      </div>
    </div>
  );
}
