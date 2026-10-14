"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Target,
  TrendingUp,
} from "lucide-react";
import { api, pct, Selection, stamp } from "@/lib/api";
import { pickLabel, marketLabel } from "@/lib/matchday";
import { ErrorBox, Skeletons, TeamBadge } from "./ui";
type Scores = {
  sample_size: number;
  brier: number | null;
  log_loss: number | null;
};
type Performance = Scores & {
  mode: string;
  count: number;
  settled: number;
  wins: number;
  win_rate: number | null;
  hypothetical_return_units: number | null;
  archive: Selection[];
  page: number;
  policy: string;
  backtest: {
    kind: string;
    reports: Record<
      string,
      { fixtures: number; markets: Record<string, Scores> }
    >;
  } | null;
};
export function Performance() {
  const [data, setData] = useState<Performance | null>(null),
    [error, setError] = useState(""),
    [page, setPage] = useState(1);
  useEffect(() => {
    let active = true;
    setError("");
    const load = () =>
      api<Performance>("/performance?page=" + page)
        .then((r) => {
          if (active) {
            setData(r);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    load();
    const interval = window.setInterval(() => {
      if (!document.hidden) load();
    }, 60000);
    return () => {
      window.clearInterval(interval);
      active = false;
    };
  }, [page]);
  return (
    <div className="container section app-page">
      <div className="page-heading">
        <div className="overline">EVERY PICK COUNTS</div>
        <h1>Our picks. The full record.</h1>
        <p>
          Follow the results of our recommended picks, from the moment we
          publish them.
        </p>
      </div>
      {error ? (
        <ErrorBox message={error} />
      ) : !data ? (
        <Skeletons />
      ) : (
        <>
          <div className="metrics">
            {[
              [
                Target,
                "Recommended picks",
                String(data.count),
                "One official pick per match",
              ],
              [
                CheckCircle2,
                "Win rate",
                data.win_rate === null ? "—" : pct(data.win_rate),
                `${data.wins} won from ${data.settled} settled`,
              ],
              [
                Clock3,
                "Awaiting a result",
                String(data.count - data.settled),
                "Includes pending, postponed & void",
              ],
              [
                TrendingUp,
                "Simulated return",
                data.hypothetical_return_units === null
                  ? "—"
                  : `${data.hypothetical_return_units > 0 ? "+" : ""}${data.hypothetical_return_units.toFixed(2)} u`,
                "At 1 unit per settled pick",
              ],
            ].map(([Icon, label, value, note]) => {
              const I = Icon as typeof Target;
              return (
                <div className="metric" key={String(label)}>
                  <span>
                    <I size={17} />
                    {String(label)}
                  </span>
                  <b>{String(value)}</b>
                  <small>{String(note)}</small>
                </div>
              );
            })}
          </div>
          <div className="performance-summary panel">
            <div>
              <div className="overline">THE BIG PICTURE</div>
              <h2>
                {data.settled
                  ? `${data.wins} wins. ${data.settled - data.wins} losses.`
                  : "The record starts before kickoff."}
              </h2>
              <p>
                {data.settled
                  ? "Every settled official pick stays in the record, including losses."
                  : "Our picks are recorded. Results will appear here once the matches finish and the score feed confirms them."}
              </p>
            </div>
            <Link className="button secondary" href="/">
              View recommended picks <ArrowUpRight size={16} />
            </Link>
          </div>
          <div className="panel archive-panel">
            <div className="section-heading">
              <div>
                <h2>Recommended pick history</h2>
                <p>Original picks and odds. Results updated when available.</p>
              </div>
              <span className="badge neutral">{data.count} picks tracked</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Match</th>
                    <th>Our pick</th>
                    <th>Odds</th>
                    <th>Estimated chance</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {data.archive.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <Link
                          className="archive-match"
                          href={"/matches/" + s.fixture_id}
                        >
                          <span>
                            <TeamBadge name={s.home} src={s.home_logo} />
                            {s.home}
                          </span>
                          <span>
                            <TeamBadge name={s.away} src={s.away_logo} />
                            {s.away}
                          </span>
                        </Link>
                        <small>{stamp(s.kickoff)}</small>
                      </td>
                      <td>
                        <b>{pickLabel(s)}</b>
                        <small>{marketLabel(s.market)}</small>
                      </td>
                      <td>
                        <b>{s.odds.toFixed(2)}</b>
                      </td>
                      <td>{pct(s.probability)}</td>
                      <td>
                        <span className={`result-badge ${s.result}`}>
                          {s.result === "pending" ? "Upcoming" : s.result}
                        </span>
                        {s.corrected && <small>Corrected result</small>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!data.archive.length && <p>No official picks published yet.</p>}
            {data.count > 30 && (
              <div className="pagination">
                <button
                  className="button secondary"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </button>
                <span>Page {page}</span>
                <button
                  className="button secondary"
                  disabled={page * 30 >= data.count}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
          <p className="fine-print">
            {data.mode === "demo"
              ? "This record uses sample fixtures and prices. It does not represent real-world results."
              : "Model estimates do not guarantee future results."}
          </p>
          <details className="method-details">
            <summary>How performance is measured</summary>
            <p>{data.policy}</p>
            <p>
              Only picks shown in our official shortlist count here. User
              parlays and other market outcomes are excluded. Recommendations
              are frozen when published and never replaced after the outcome is
              known.
            </p>
            <div className="stat-list">
              <div>
                <span>Brier score</span>
                <b>{data.brier?.toFixed(3) || "Awaiting results"}</b>
              </div>
              <div>
                <span>Log loss</span>
                <b>{data.log_loss?.toFixed(3) || "Awaiting results"}</b>
              </div>
            </div>
            <p>
              Lower scores are better. Returns are simulations, not placed bets.
            </p>
          </details>
          <details className="method-details">
            <summary>Historical model evaluation</summary>
            {data.backtest ? (
              <>
                <p>
                  {data.backtest.kind} · Separate from the official pick record
                  above.
                </p>
                {Object.entries(data.backtest.reports).map(([name, r]) => (
                  <div key={name}>
                    <h3>
                      {name} · {r.fixtures} matches
                    </h3>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Market</th>
                            <th>Samples</th>
                            <th>Brier score</th>
                            <th>Log loss</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(r.markets).map(([m, s]) => (
                            <tr key={m}>
                              <td>{marketLabel(m)}</td>
                              <td>{s.sample_size}</td>
                              <td>{s.brier?.toFixed(3) || "—"}</td>
                              <td>{s.log_loss?.toFixed(3) || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <p>No historical evaluation recorded yet.</p>
            )}
          </details>
        </>
      )}
    </div>
  );
}
