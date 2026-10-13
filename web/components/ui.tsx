"use client";
import clubCrests from "@/lib/clubs.json";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Bookmark, Check, Plus, Info } from "lucide-react";
import { api, initials, pct, Selection, stamp } from "@/lib/api";
import { Pick, pickKey, pickLabel, marketLabel } from "@/lib/matchday";
import { useApp } from "./shell";
import { useParlay } from "./parlay-context";
export function ErrorBox({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <Info size={18} />
      <span>{message}</span>
      {retry && (
        <button className="text-button" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function Skeletons() {
  return (
    <div
      className="card-grid"
      aria-label="Loading predictions"
      aria-busy="true"
    >
      {[0, 1, 2].map((i) => (
        <div className="prediction-card skeleton" key={i}>
          <div />
          <div />
          <div />
        </div>
      ))}
    </div>
  );
}
export function Empty({
  title = "No matching selections",
  children,
}: {
  title?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">⚽</div>
      <h3>{title}</h3>
      <p>{children || "Try another date, team or market."}</p>
    </div>
  );
}
export function TeamBadge({
  name,
  away = false,
  src,
}: {
  name: string;
  away?: boolean;
  src?: string | null;
}) {
  const [failed, setFailed] = useState(false);
  const local = (clubCrests as Record<string, string>)[name];
  return (
    <span className={`team-badge ${away ? "away" : ""}`}>
      {!failed && (src || local) ? (
        <img
          src={src || local}
          alt={`${name} crest`}
          width={36}
          height={36}
          onError={() => setFailed(true)}
        />
      ) : (
        <span aria-label={name}>{initials(name)}</span>
      )}
    </span>
  );
}
export function AddPick({
  pick,
  small = false,
}: {
  pick: Pick;
  small?: boolean;
}) {
  const { picks, toggle } = useParlay(),
    selected = picks.some((p) => pickKey(p) === pickKey(pick));
  const closed = new Date(pick.kickoff).getTime() <= Date.now();
  return (
    <button
      className={`button ${selected ? "selected" : "secondary"} ${small ? "small" : ""}`}
      onClick={() => toggle(pick)}
      disabled={closed}
      aria-pressed={selected}
      aria-label={`${selected ? "Remove" : "Add"} ${pickLabel(pick)} ${selected ? "from" : "to"} parlay`}
    >
      {selected ? <Check size={15} /> : <Plus size={15} />}{" "}
      {closed
        ? "Match started"
        : selected
          ? "Added"
          : small
            ? "Add"
            : "Add to parlay"}
    </button>
  );
}
export function PredictionCard({
  s,
  compact = false,
  rank,
  oddsLabel = "Current odds",
}: {
  s: Selection;
  compact?: boolean;
  rank?: number;
  oddsLabel?: string;
}) {
  const { user } = useApp(),
    router = useRouter();
  const [saved, setSaved] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pick: Pick = {
    ...s,
    publication_id: s.id,
    prices: [{ bookmaker: s.bookmaker, odds: s.odds, stale: s.stale }],
  };
  async function save() {
    if (!user) {
      router.push(
        "/account?next=" + encodeURIComponent(window.location.pathname),
      );
      return;
    }
    setBusy(true);
    try {
      await api("/saved", {
        method: "POST",
        body: JSON.stringify({ publication_id: s.id }),
      });
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article
      className={`prediction-card ${compact ? "compact" : ""}`}
      data-kickoff={s.kickoff}
    >
      <div className="card-top">
        <span className="eyebrow">
          {rank
            ? `PICK ${String(rank).padStart(2, "0")} · ${s.competition}`
            : s.competition}
        </span>
        <button
          className="icon-button"
          onClick={save}
          disabled={busy || saved}
          aria-label={`Save ${s.home} ${s.outcome}`}
        >
          {saved ? <Check size={16} /> : <Bookmark size={16} />}
        </button>
      </div>
      <Link className="teams" href={"/matches/" + s.fixture_id}>
        <div>
          <TeamBadge name={s.home} src={s.home_logo} />
          <strong>{s.home}</strong>
        </div>
        <div>
          <TeamBadge name={s.away} src={s.away_logo} away />
          <strong>{s.away}</strong>
        </div>
      </Link>
      <div className="kickoff">
        {stamp(s.kickoff, user?.preferences.timezone)}
      </div>
      <div className="selection">
        <div>
          <span>{marketLabel(s.market)}</span>
          <strong>{pickLabel(s)}</strong>
        </div>
        <div className="price">
          <strong>{s.odds.toFixed(2)}</strong>
          <small>{s.mode === "demo" ? "Sample odds" : oddsLabel}</small>
        </div>
      </div>
      <div className="probability">
        <div>
          <span>Model chance</span>
          <strong>{pct(s.probability)}</strong>
        </div>
        <div className="probability-track">
          <span style={{ width: pct(s.probability) }} />
        </div>
      </div>
      {s.analysis && (
        <details className="card-reason">
          <summary>Why this pick?</summary>
          <p>{s.analysis.summary}</p>
        </details>
      )}
      <div className="pick-book">{s.bookmaker}</div>
      <div className="card-bottom">
        <Link href={"/matches/" + s.fixture_id}>
          Analysis <ArrowUpRight size={14} />
        </Link>
        <AddPick pick={pick} small />
      </div>
      {error && <ErrorBox message={error} />}
    </article>
  );
}
