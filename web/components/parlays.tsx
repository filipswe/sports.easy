"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, ArrowRight, Layers3, Trash2 } from "lucide-react";
import { api, pct, stamp } from "@/lib/api";
import { Parlay, pickLabel } from "@/lib/matchday";
import { useParlay } from "./parlay-context";
import { ParlayPanel } from "./parlay-panel";
import { Empty, ErrorBox, Skeletons, TeamBadge } from "./ui";
type SavedParlay = Parlay & { saved_at: string };
export function Parlays() {
  const { replace } = useParlay();
  const [items, setItems] = useState<Parlay[] | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [legs, setLegs] = useState(3),
    [min, setMin] = useState("3"),
    [max, setMax] = useState("12"),
    [tab, setTab] = useState("Suggested parlays"),
    [saved, setSaved] = useState<SavedParlay[]>([]),
    [loaded, setLoaded] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    api<{ items: Parlay[] }>(
      "/parlays/suggestions?legs=3&min_odds=3&max_odds=12",
    )
      .then((r) => {
        if (active) setItems(r.items);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function suggest(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    setLoaded(null);
    try {
      const r = await api<{ items: Parlay[] }>(
        `/parlays/suggestions?legs=${legs}&min_odds=${min}&max_odds=${max}`,
      );
      setItems(r.items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openSaved() {
    setTab("Saved parlays");
    try {
      const s = JSON.parse(
        localStorage.getItem("sports-easy-saved-parlays") || "[]",
      );
      setSaved(Array.isArray(s) ? s : []);
    } catch {
      setSaved([]);
    }
  }
  function removeSaved(index: number) {
    const remaining = saved.filter((_, i) => i !== index);
    try {
      localStorage.setItem(
        "sports-easy-saved-parlays",
        JSON.stringify(remaining),
      );
      setSaved(remaining);
    } catch {
      setError("Could not update saved parlays.");
    }
  }
  return (
    <div className="container section app-page">
      <div className="page-heading">
        <div className="overline">
          <Layers3 size={15} /> A FEW PICKS. ONE PICTURE.
        </div>
        <h1>Make it your parlay.</h1>
        <p>
          Start with a model suggestion or combine your own picks. See the odds
          and the chance of them all winning.
        </p>
      </div>
      <div className="browse-layout">
        <div>
          <div className="tabs page-tabs">
            <button
              className={tab === "Suggested parlays" ? "active" : ""}
              onClick={() => setTab("Suggested parlays")}
            >
              Suggested parlays
            </button>
            <button
              className={tab === "Saved parlays" ? "active" : ""}
              onClick={openSaved}
            >
              Saved parlays
            </button>
            <Link href="/predictions" className="text-link">
              Choose my own <ArrowRight size={15} />
            </Link>
          </div>
          {tab === "Suggested parlays" ? (
            <>
              <form className="parlay-controls panel" onSubmit={suggest}>
                <label>
                  Number of picks
                  <select
                    value={legs}
                    onChange={(e) => setLegs(Number(e.target.value))}
                  >
                    {[2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n} picks
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Min. combined odds
                  <input
                    type="number"
                    min="1.01"
                    max="1000"
                    step="0.01"
                    value={min}
                    onChange={(e) => setMin(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Max. combined odds
                  <input
                    type="number"
                    min={min}
                    max="1000"
                    step="0.01"
                    value={max}
                    onChange={(e) => setMax(e.target.value)}
                    required
                  />
                </label>
                <button className="button primary" disabled={busy}>
                  <Sparkles size={15} />
                  {busy ? "Finding picks…" : "Find parlays"}
                </button>
              </form>
              <p className="hint">
                Suggestions rank the combinations found by model chance within
                your odds range.
              </p>
              {error ? (
                <ErrorBox message={error} />
              ) : items === null ? (
                <Skeletons />
              ) : !items.length ? (
                <Empty title="No parlays in that range">
                  Try a wider odds range or fewer picks. Suggestions use
                  available sportsbook prices.
                </Empty>
              ) : (
                <div className="suggestions">
                  {items.map((p, i) => (
                    <article className="panel parlay-suggestion" key={i}>
                      <div className="section-heading">
                        <div className="overline">
                          <Sparkles size={14} />{" "}
                          {i === 0
                            ? "TOP MODEL SUGGESTION"
                            : `ANOTHER COMBINATION · 0${i + 1}`}
                        </div>
                        <span className="badge neutral">
                          {p.legs.length} picks
                        </span>
                      </div>
                      {p.legs.map((l) => (
                        <div className="suggestion-leg" key={l.fixture_id}>
                          <div>
                            <TeamBadge name={l.home} src={l.home_logo} />
                            <TeamBadge name={l.away} src={l.away_logo} />
                          </div>
                          <div>
                            <Link href={"/matches/" + l.fixture_id}>
                              {l.home} – {l.away}
                            </Link>
                            <strong>{pickLabel(l)}</strong>
                          </div>
                          <b>{l.odds?.toFixed(2)}</b>
                        </div>
                      ))}
                      <div className="suggestion-footer">
                        <div>
                          <small>Combined odds</small>
                          <b>{p.combined_odds?.toFixed(2)}</b>
                        </div>
                        <div>
                          <small>Model chance · all win</small>
                          <b>{pct(p.probability)}</b>
                        </div>
                        <button
                          className="button primary"
                          onClick={() => {
                            replace(p.legs);
                            setLoaded(i);
                            if (window.matchMedia("(max-width: 900px)").matches)
                              document
                                .getElementById("my-parlay")
                                ?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "start",
                                });
                          }}
                        >
                          {loaded === i ? "Loaded ✓" : "Use this parlay"}
                        </button>
                      </div>
                      <p className="fine-print">
                        {p.mode === "demo" ? "Sample prices" : "Recorded odds"}
                        {p.mode !== "demo" &&
                        p.prices.some((price) => price.stale)
                          ? " · Prices outdated"
                          : ""}{" "}
                        · Assumes independent matches. All picks must win.
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              <p className="hint">
                Saved on this browser. Open a parlay to refresh its analysis.
              </p>
              {!saved.length ? (
                <Empty title="No saved parlays yet">
                  Build a parlay and choose “Save this parlay”.
                </Empty>
              ) : (
                saved.map((p, i) => (
                  <div className="panel saved-parlay" key={p.saved_at}>
                    <div>
                      <h3>
                        {p.legs.length}-pick parlay ·{" "}
                        {p.combined_odds?.toFixed(2) || "No price"}
                      </h3>
                      <p>{stamp(p.saved_at)}</p>
                      {p.legs.map((l) => (
                        <p key={l.fixture_id}>{pickLabel(l)}</p>
                      ))}
                    </div>
                    <button
                      className="button secondary"
                      onClick={() => replace(p.legs)}
                    >
                      Open parlay
                    </button>
                    <button
                      className="icon-button"
                      aria-label="Delete saved parlay"
                      onClick={() => removeSaved(i)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))
              )}
            </>
          )}
        </div>
        <ParlayPanel full />
      </div>
    </div>
  );
}
