"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Sparkles,
  Layers3,
  CircleCheck,
  ChartNoAxesCombined,
} from "lucide-react";
import { api, Selection, pct } from "@/lib/api";
import { useApp } from "./shell";
import { AnalystChat } from "./analyst-chat";
import { Empty, ErrorBox, PredictionCard, Skeletons, TeamBadge } from "./ui";
export function Home() {
  const { meta } = useApp();
  const [items, setItems] = useState<Selection[] | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () =>
      api<{ items: Selection[] }>("/recommendations")
        .then((r) => {
          if (active) {
            setItems(r.items);
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
      active = false;
      window.clearInterval(interval);
    };
  }, []);
  const top = items?.[0];
  return (
    <>
      <section className="hero container">
        <div className="hero-copy">
          <div className="overline">
            <span className="status-dot" /> YOUR MATCHDAY ADVANTAGE
          </div>
          <h1>
            Betting made
            <br />
            <em>easy.</em>
          </h1>
          <p>
            Find your next pick. Get the match insight.
            <br className="desktop-only" /> Build a parlay that makes sense to
            you.
          </p>
          <div className="hero-actions">
            <Link className="button primary" href="/predictions">
              Explore matches <ArrowUpRight size={18} />
            </Link>
            <Link className="button secondary" href="/parlays">
              Build a parlay <Layers3 size={17} />
            </Link>
          </div>
          <div className="hero-notes">
            <span>
              <CircleCheck size={15} /> Picks backed by match data
            </span>
            <span>
              <ChartNoAxesCombined size={15} /> Every recommendation tracked
            </span>
          </div>
        </div>
        <div className="matchday-visual">
          <div className="visual-heading">
            <span>
              <span className="status-dot" /> THE MATCHDAY EDIT
            </span>
            <span>01 — FOOTBALL</span>
          </div>
          <div className="visual-pitch">
            <div className="center-circle" />
            <div className="penalty-box left" />
            <div className="penalty-box right" />
            <span className="pitch-dot p1" />
            <span className="pitch-dot p2" />
            <span className="pitch-dot p3" />
          </div>
          <div className="hero-match">
            <span className="badge green-badge">
              <Sparkles size={12} /> Matchday spotlight
            </span>
            {top ? (
              <>
                <div className="hero-match-teams">
                  <div>
                    <TeamBadge name={top.home} src={top.home_logo} />
                    <b>{top.home}</b>
                  </div>
                  <span>VS</span>
                  <div>
                    <TeamBadge name={top.away} src={top.away_logo} />
                    <b>{top.away}</b>
                  </div>
                </div>
                <div className="hero-match-footer">
                  <span>First kickoff in our shortlist</span>
                  <strong>
                    {pct(top.probability)}
                    <small>
                      {top.probability_basis?.toLowerCase() || "model chance"}
                    </small>
                  </strong>
                </div>
              </>
            ) : (
              <div className="hero-match-teams">
                <b>Your next matchday starts here.</b>
              </div>
            )}
          </div>
          <div className="visual-caption">
            <span>LESS NOISE. MORE FOOTBALL.</span>
            <ArrowUpRight size={19} />
          </div>
        </div>
      </section>
      <div className="coverage-strip">
        <div className="container">
          <span>ON THE PITCH</span>
          <strong>⚽ Europe’s top five leagues</strong>
          <span className="strip-divider" />
          <span>1X2</span>
          <span>Both teams to score</span>
          <span>Goal markets</span>
          <span>First half</span>
          <span className="coverage-mode">PRE-MATCH</span>
        </div>
      </div>
      <section className="container section">
        <div className="section-heading">
          <div>
            <div className="overline">
              <Sparkles size={14} /> THE SHORTLIST
            </div>
            <h2>Our recommended picks</h2>
            <p>
              Our picks for the soonest matchday, in kickoff order. European
              nights and the top five leagues, as they happen.
            </p>
          </div>
          <Link className="text-link" href="/performance">
            See our record <ArrowRight size={17} />
          </Link>
        </div>
        {error ? (
          <ErrorBox message={error} />
        ) : items === null ? (
          <Skeletons />
        ) : items.length ? (
          <div className="recommended-grid">
            {items.map((s, i) => (
              <PredictionCard key={s.id} s={s} rank={i + 1} />
            ))}
          </div>
        ) : (
          <Empty title="The next shortlist is on its way">
            Picks appear when upcoming matches have enough data and available
            prices.{" "}
            <Link href="/predictions" className="text-link">
              Browse all matches →
            </Link>
          </Empty>
        )}
        <p className="fine-print">
          {meta?.mode === "demo"
            ? "Sample fixtures and odds are shown while the live feed is disconnected. "
            : ""}
          Model chances are estimates. No pick is guaranteed.
        </p>
      </section>
      <AnalystChat />
      <section className="container section">
        <div className="section-heading">
          <div>
            <div className="overline">FROM KICKOFF TO CLARITY</div>
            <h2>A simpler way to pick.</h2>
          </div>
          <Link href="/how-it-works" className="text-link">
            How it works <ArrowRight size={16} />
          </Link>
        </div>
        <div className="steps">
          {[
            [
              "01",
              "Find your match",
              "Browse fixtures, check recent results, and see what the model thinks.",
            ],
            [
              "02",
              "Make it your own",
              "Choose a result or goals market. See its estimated chance and sportsbook price.",
            ],
            [
              "03",
              "Keep the full picture",
              "Build your parlay and follow the results of our official recommended picks.",
            ],
          ].map(([n, title, text]) => (
            <div className="step" key={n}>
              <span className="step-number">{n}</span>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
