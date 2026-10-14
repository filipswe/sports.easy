"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Layers3, Trash2, X, BookmarkCheck } from "lucide-react";
import { api, pct } from "@/lib/api";
import { Parlay, pickKey, pickLabel } from "@/lib/matchday";
import { useParlay } from "./parlay-context";
import { ErrorBox, TeamBadge } from "./ui";
export function ParlayPanel({ full = false }: { full?: boolean }) {
  const { picks, remove, clear, message } = useParlay();
  const [analysis, setAnalysis] = useState<Parlay | null>(null),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false),
    [entered, setEntered] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    setAnalysis(null);
    setSaved(false);
    setError("");
    if (!picks.length) return;
    setBusy(true);
    const timer = setTimeout(() => {
      api<Parlay>("/parlays/analyze", {
        method: "POST",
        body: JSON.stringify({
          legs: picks.map((p) => ({
            fixture_id: p.fixture_id,
            market: p.market,
            outcome: p.outcome,
            user_odds:
              (entered[pickKey(p)] ?? p.user_odds?.toString())
                ? Number(entered[pickKey(p)] ?? p.user_odds)
                : null,
          })),
        }),
      })
        .then((r) => {
          if (active) setAnalysis(r);
        })
        .catch((e) => {
          if (active) setError(e.message);
        })
        .finally(() => {
          if (active) setBusy(false);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [picks, entered]);
  function save() {
    if (!analysis) return;
    try {
      const records = JSON.parse(
        localStorage.getItem("sports-easy-saved-parlays") || "[]",
      );
      localStorage.setItem(
        "sports-easy-saved-parlays",
        JSON.stringify(
          [
            { ...analysis, saved_at: new Date().toISOString() },
            ...(Array.isArray(records) ? records : []),
          ].slice(0, 30),
        ),
      );
      setSaved(true);
    } catch {
      setError("This browser could not save your parlay.");
    }
  }
  const chance = analysis?.probability;
  return (
    <aside
      className={`slip panel ${full ? "full-slip" : ""}`}
      aria-label="My parlay"
      id="my-parlay"
    >
      <div className="slip-heading">
        <h2>
          <Layers3 size={19} /> My parlay <span>{picks.length}</span>
        </h2>
        {picks.length > 0 && (
          <button
            className="icon-button"
            onClick={clear}
            aria-label="Clear parlay"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>
      {!picks.length ? (
        <div className="slip-empty">
          <div className="slip-icon">
            <Layers3 size={30} />
          </div>
          <h3>Your picks start here</h3>
          <p>
            Tap a match outcome to add it.
            <br />
            Combine picks from different matches.
          </p>
          {full && (
            <Link className="button primary" href="/predictions">
              Browse matches →
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="slip-legs">
            {picks.map((p, i) => (
              <div className="slip-leg" key={pickKey(p)}>
                <div className="slip-leg-top">
                  <span>SELECTION {i + 1}</span>
                  <button
                    className="icon-button"
                    onClick={() => remove(pickKey(p))}
                    aria-label={`Remove ${pickLabel(p)}`}
                  >
                    <X size={15} />
                  </button>
                </div>
                <div className="slip-fixture">
                  <TeamBadge name={p.home} src={p.home_logo} />
                  <Link href={"/matches/" + p.fixture_id}>
                    {p.home} – {p.away}
                  </Link>
                </div>
                <div className="slip-pick">
                  <strong>{pickLabel(p)}</strong>
                  <b>{p.odds?.toFixed(2) || "—"}</b>
                </div>
                {full && (
                  <label className="entered-odds">
                    Your decimal odds (optional)
                    <input
                      type="number"
                      min="1.01"
                      max="1000"
                      step="0.01"
                      placeholder={p.odds?.toFixed(2) || "Enter price"}
                      value={
                        entered[pickKey(p)] ?? p.user_odds?.toString() ?? ""
                      }
                      onChange={(e) =>
                        setEntered({ ...entered, [pickKey(p)]: e.target.value })
                      }
                    />
                  </label>
                )}
              </div>
            ))}
          </div>
          {error && <ErrorBox message={error} />}
          <div className="slip-totals">
            <div>
              <span>Combined odds</span>
              <strong>
                {busy ? "…" : analysis?.combined_odds?.toFixed(2) || "—"}
              </strong>
            </div>
            <div>
              <span>Estimated chance · all win</span>
              <b>{busy ? "…" : chance !== undefined ? pct(chance) : "—"}</b>
            </div>
            {chance != null && (
              <div className="probability-track">
                <span style={{ width: pct(chance) }} />
              </div>
            )}
            {analysis && (
              <p>
                {analysis.probability === null
                  ? "Model confidence is unavailable for one or more picks. "
                  : ""}
                {analysis.mode === "demo"
                  ? "Sample prices"
                  : analysis.odds_basis === "Your entered prices" ||
                      !analysis.combined_odds
                    ? analysis.odds_basis
                    : `Current odds · ${analysis.odds_basis}`}
                . {analysis.approximation}
              </p>
            )}
            {analysis && !analysis.combined_odds && (
              <p>
                Odds are missing for one or more picks. Enter a price for every
                leg to calculate your own total.
              </p>
            )}
            {analysis &&
              picks.some((p) => entered[pickKey(p)]) &&
              !picks.every((p) => entered[pickKey(p)]) && (
                <p>
                  Enter odds for every pick to use your own prices. The
                  displayed total uses the connected source.
                </p>
              )}
          </div>
          {full ? (
            <button
              className="button primary wide"
              onClick={save}
              disabled={!analysis || saved}
            >
              <BookmarkCheck size={16} />
              {saved ? "Saved on this device" : "Save this parlay"}
            </button>
          ) : (
            <Link className="button primary wide" href="/parlays">
              Review parlay →
            </Link>
          )}
        </>
      )}
      {message && (
        <p className="slip-message" role="status">
          {message}
        </p>
      )}
      <div className="slip-bottom">
        One pick per match · No bets are placed here
      </div>
    </aside>
  );
}
