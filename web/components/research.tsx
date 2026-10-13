"use client";
import { useEffect, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowUpRight,
  Search,
  RotateCcw,
  SlidersHorizontal,
  Info,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api, Selection } from "@/lib/api";
import { useApp } from "./shell";
import { Empty, ErrorBox, PredictionCard, Skeletons } from "./ui";
type Results = {
  items: Selection[];
  total: number;
  page: number;
  page_size: number;
  ranking: string;
};
const defaults = {
  min_odds: "1.01",
  max_odds: "1000",
  market: "all",
  team: "",
  league: "",
  bookmaker: "",
  region: "uk",
  period: "week",
  min_probability: "0",
  sort: "kickoff",
  target: "",
  tolerance: "0.10",
  start: "",
  end: "",
  positive_ev: false,
  fresh_only: false,
};
type State = typeof defaults;
export function Research({ builder = false }: { builder?: boolean }) {
  const params = useSearchParams(),
    router = useRouter(),
    { meta } = useApp();
  const [form, setForm] = useState<State>(defaults),
    [data, setData] = useState<Results | null>(null),
    [busy, setBusy] = useState(true),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  const query = params.toString();
  useEffect(() => {
    const p = new URLSearchParams(query);
    const next = { ...defaults };
    for (const k of Object.keys(defaults) as (keyof State)[]) {
      const v = p.get(k);
      if (v !== null) {
        if (k === "positive_ev" || k === "fresh_only") next[k] = v === "true";
        else next[k] = v;
      }
    }
    if (next.period === "custom") {
      const localDate = (value: string, subtractDay = false) => {
        const d = new Date(value);
        if (!Number.isFinite(d.getTime())) return "";
        if (subtractDay) d.setDate(d.getDate() - 1);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      };
      if (next.start) next.start = localDate(next.start);
      if (next.end) next.end = localDate(next.end, true);
    }
    setForm(next);
    setBusy(true);
    setError("");
    const controller = new AbortController();
    api<Results>("/research?" + query, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [query, retry]);
  function update(key: keyof State, value: string | boolean) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function submit(e?: FormEvent) {
    e?.preventDefault();
    if (Number(form.min_odds) > Number(form.max_odds)) {
      setError("Minimum odds must be less than or equal to maximum odds.");
      return;
    }
    const p = new URLSearchParams();
    Object.entries(form).forEach(([k, v]) => {
      if (v !== "" && v !== false) p.set(k, String(v));
    });
    if (form.period === "today" || form.period === "tomorrow") {
      const start = new Date();
      start.setHours(0, 0, 0, 0);
      if (form.period === "tomorrow") start.setDate(start.getDate() + 1);
      const end = new Date(start);
      end.setDate(end.getDate() + 1);
      p.set("start", start.toISOString());
      p.set("end", end.toISOString());
    } else if (form.period === "custom") {
      if (!form.start || !form.end) {
        setError("Choose both custom dates.");
        return;
      }
      p.set("start", new Date(form.start + "T00:00:00").toISOString());
      const end = new Date(form.end + "T00:00:00");
      end.setDate(end.getDate() + 1);
      p.set("end", end.toISOString());
    } else {
      p.delete("start");
      p.delete("end");
    }
    router.push((builder ? "/research" : "/predictions") + "?" + p);
  }
  function page(n: number) {
    const p = new URLSearchParams(query);
    p.set("page", String(n));
    router.push((builder ? "/research" : "/predictions") + "?" + p);
  }
  function preset(min: string, max: string) {
    setForm((f) => ({ ...f, min_odds: min, max_odds: max, target: "" }));
  }
  return (
    <div className="container section">
      <div className="page-heading">
        <div className="overline">
          {builder ? "BUILD A BETTER QUESTION" : "FOOTBALL / PRE-MATCH"}
        </div>
        <h1>
          {builder
            ? "Your range. Your research."
            : "The next match starts here."}
        </h1>
        <p>
          {builder
            ? "Find single selections that fit your criteria. Understand why they match."
            : "Explore upcoming matches through prices, probabilities and the data behind them."}
        </p>
      </div>
      <div className="research-layout">
        <form className="filter-panel" onSubmit={submit}>
          <div className="filter-title">
            <h2>
              <SlidersHorizontal size={18} />
              {builder ? "Research Builder" : "Filters"}
            </h2>
            <button
              type="button"
              title="Reset filters"
              className="icon-button"
              onClick={() => {
                setForm(defaults);
                router.push(builder ? "/research" : "/predictions");
              }}
            >
              <RotateCcw size={15} />
            </button>
          </div>
          {builder && (
            <p className="badge green-badge">Single-selection mode</p>
          )}
          <fieldset>
            <legend>Decimal odds</legend>
            <div className="input-pair">
              <label>
                Minimum
                <input
                  name="min_odds"
                  type="number"
                  min="1.01"
                  max="1000"
                  step="0.01"
                  value={form.min_odds}
                  onChange={(e) => update("min_odds", e.target.value)}
                  required
                />
              </label>
              <label>
                Maximum
                <input
                  name="max_odds"
                  type="number"
                  min="1.01"
                  max="1000"
                  step="0.01"
                  value={form.max_odds}
                  onChange={(e) => update("max_odds", e.target.value)}
                  required
                />
              </label>
            </div>
            <div className="presets">
              {[
                ["1.10", "1.30"],
                ["1.30", "1.75"],
                ["1.75", "3.00"],
                ["3.00", "5.00"],
                ["5.00", "1000"],
              ].map(([min, max]) => (
                <button
                  type="button"
                  key={min}
                  className={
                    form.min_odds === min && form.max_odds === max
                      ? "selected"
                      : ""
                  }
                  onClick={() => preset(min, max)}
                >
                  {max === "1000" ? "5.00+" : min + "–" + max}
                </button>
              ))}
            </div>
            <p className="hint">Payout ranges, not confidence categories.</p>
            {builder && (
              <div className="input-pair">
                <label>
                  Target (optional)
                  <input
                    type="number"
                    min="1.01"
                    max="1000"
                    step="0.01"
                    placeholder="e.g. 2.00"
                    value={form.target}
                    onChange={(e) => update("target", e.target.value)}
                  />
                </label>
                <label>
                  Tolerance ±
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="0.01"
                    value={form.tolerance}
                    onChange={(e) => update("tolerance", e.target.value)}
                  />
                </label>
              </div>
            )}
          </fieldset>
          <fieldset>
            <legend>Match & market</legend>
            <label>
              Dates
              <select
                value={form.period}
                onChange={(e) => update("period", e.target.value)}
              >
                <option value="today">Today</option>
                <option value="tomorrow">Tomorrow</option>
                <option value="week">Next 7 Days</option>
                <option value="custom">Custom dates</option>
              </select>
            </label>
            {form.period === "custom" && (
              <div className="input-pair">
                <label>
                  From
                  <input
                    type="date"
                    value={form.start.slice(0, 10)}
                    onChange={(e) => update("start", e.target.value)}
                  />
                </label>
                <label>
                  Through
                  <input
                    type="date"
                    value={form.end.slice(0, 10)}
                    onChange={(e) => update("end", e.target.value)}
                  />
                </label>
              </div>
            )}
            <label>
              Competition
              <select
                value={form.league}
                onChange={(e) => update("league", e.target.value)}
              >
                <option value="">All supported competitions</option>
                {meta?.leagues.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name} · {l.season}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Search teams
              <div className="search-input">
                <Search size={15} />
                <input
                  placeholder="Team name"
                  value={form.team}
                  onChange={(e) => update("team", e.target.value)}
                  maxLength={80}
                />
              </div>
            </label>
            <label>
              Market
              <select
                value={form.market}
                onChange={(e) => update("market", e.target.value)}
              >
                <option value="all">All available markets</option>
                <option value="1x2">Match result · 1X2</option>
                <option value="totals">Over / under 2.5</option>
                <option value="btts">Both teams to score</option>
              </select>
            </label>
          </fieldset>
          <fieldset>
            <legend>Price source</legend>
            <label>
              Bookmaker region
              <select
                value={form.region}
                onChange={(e) => update("region", e.target.value)}
              >
                {["uk", "eu", "us", "au"].map((r) => (
                  <option key={r} value={r}>
                    {r.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Bookmaker
              <select
                value={form.bookmaker}
                onChange={(e) => update("bookmaker", e.target.value)}
              >
                <option value="">Best quote in selected region</option>
                {meta?.bookmakers
                  .filter((b) => b.region === form.region)
                  .map((b) => (
                    <option value={b.id} key={b.id}>
                      {b.name}
                    </option>
                  ))}
              </select>
            </label>
          </fieldset>
          <fieldset>
            <legend>Model & freshness</legend>
            <label>
              Minimum estimated probability{" "}
              <span className="green">
                {Math.round(Number(form.min_probability) * 100)}%
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={form.min_probability}
                onChange={(e) => update("min_probability", e.target.value)}
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.positive_ev}
                onChange={(e) => update("positive_ev", e.target.checked)}
              />
              Positive estimated EV only
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.fresh_only}
                onChange={(e) => update("fresh_only", e.target.checked)}
              />
              Fresh quotes only
            </label>
            <p className="hint">
              Source age ≤ {meta ? meta.freshness_seconds / 60 : 10} minutes.
              Stale quotes never enter current-EV rankings.
            </p>
          </fieldset>
          <label>
            Rank results by
            <select
              value={form.sort}
              onChange={(e) => update("sort", e.target.value)}
            >
              <option value="kickoff">Kickoff time</option>
              <option value="probability">Highest estimated probability</option>
              <option value="ev">Highest estimated EV</option>
              <option value="odds">Highest odds</option>
              <option value="freshness">Freshest source update</option>
            </select>
          </label>
          <button className="button primary full" disabled={busy} type="submit">
            {busy ? "Searching records…" : "Find predictions"}
            <ArrowUpRight size={17} />
          </button>
          <button
            type="button"
            className="text-button full"
            onClick={() => {
              setForm(defaults);
              router.push(builder ? "/research" : "/predictions");
            }}
          >
            Reset filters
          </button>
        </form>
        <section className="research-results" aria-label="Research results">
          <div className="results-heading">
            <div>
              <h2>
                {builder ? "Matching selections" : "Upcoming predictions"}
              </h2>
              <p>
                {data ? `${data.total} selections · ` : ""}90-minute regulation
                time
              </p>
            </div>
            <span className="badge neutral">
              {meta?.mode === "demo" ? "Demo dataset" : "Provider dataset"}
            </span>
          </div>
          <div className="notice">
            <Info size={18} />
            <span>
              Probability and expected value answer different questions. A
              higher estimated EV does not mean a higher chance of winning.
            </span>
          </div>
          {error && (
            <ErrorBox message={error} retry={() => setRetry((n) => n + 1)} />
          )}
          <div aria-live="polite">
            {busy ? (
              <Skeletons />
            ) : data?.items.length ? (
              <>
                <p className="hint result-policy">
                  Ranked by {data.ranking}. Prices are available stored quotes,
                  never manufactured to meet a target.
                </p>
                <div className="card-grid">
                  {data.items.map((s) => (
                    <PredictionCard key={s.id} s={s} />
                  ))}
                </div>
              </>
            ) : (
              <Empty />
            )}
          </div>
          {data && data.total > data.page_size && (
            <div className="pagination">
              <button
                className="button secondary"
                disabled={data.page === 1 || busy}
                onClick={() => page(data.page - 1)}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <span>
                Page {data.page} of {Math.ceil(data.total / data.page_size)}
              </span>
              <button
                className="button secondary"
                disabled={data.page * data.page_size >= data.total || busy}
                onClick={() => page(data.page + 1)}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
          <p className="fine-print">
            Estimated failure probability is the chance of losing this selection
            under the model. It is not a complete measure of financial risk. All
            estimates are unvalidated.
          </p>
        </section>
      </div>
    </div>
  );
}
