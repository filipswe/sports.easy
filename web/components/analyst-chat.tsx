"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ArrowUpRight, MessageCircle, Send } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { MatchRow } from "@/lib/matchday";

type Answer = { label: string; answer: string; notice: string; match: string };

export function AnalystChat() {
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [fixture, setFixture] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<{ items: MatchRow[] }>("/matchday?period=fortnight")
      .then(({ items }) => {
        if (!active) return;
        setMatches(items);
        setFixture(items[0]?.id || "");
      })
      .catch(() => {
        if (active) setError("Match data is temporarily unavailable.");
      });
    return () => {
      active = false;
    };
  }, []);
  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !fixture || question.trim().length < 2) return;
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(
        await api<Answer>("/chat", {
          method: "POST",
          body: JSON.stringify({
            fixture_id: fixture,
            question: question.trim(),
          }),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to answer. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="container section analyst-section"
      aria-labelledby="analyst-title"
    >
      <div className="analyst-copy">
        <div className="overline">
          <MessageCircle size={15} /> ASK ABOUT YOUR PICK
        </div>
        <h2 id="analyst-title">
          A little insight.
          <br />A clearer decision.
        </h2>
        <p>
          Ask about the odds, recent form or why the model favors a pick. Start
          with a match.
        </p>
        <Link href="/parlays" className="text-link">
          Ready to combine your picks? <ArrowUpRight size={16} />
        </Link>
      </div>
      <div className="analyst-card panel">
        <form onSubmit={ask}>
          <label htmlFor="analyst-match">Your match</label>
          <select
            id="analyst-match"
            value={fixture}
            disabled={busy || !matches.length}
            onChange={(e) => {
              setFixture(e.target.value);
              setAnswer(null);
            }}
          >
            {!matches.length && (
              <option value="">No priced matches available yet</option>
            )}
            {matches.map((m) => (
              <option key={m.id} value={m.id}>
                {m.home} vs {m.away} · {m.competition}
              </option>
            ))}
          </select>
          <label htmlFor="analyst-question">What would you like to know?</label>
          <textarea
            id="analyst-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={600}
            minLength={2}
            rows={3}
            required
            placeholder="Why does the model favor this pick?"
            disabled={busy}
          />
          <div className="analyst-prompts">
            {[
              "Why does the model favor this pick?",
              "What is the recent form?",
              "What are the current odds?",
            ].map((q) => (
              <button
                type="button"
                key={q}
                disabled={busy}
                onClick={() => setQuestion(q)}
              >
                {q}
              </button>
            ))}
          </div>
          <button
            className="button primary"
            type="submit"
            disabled={busy || !fixture || question.trim().length < 2}
          >
            <Send size={15} />{" "}
            {busy ? "Checking match insight…" : "Ask our analyst"}
          </button>
        </form>
        <div aria-live="polite" aria-atomic="true">
          {error && (
            <p role="alert" className="error-box">
              {error}
            </p>
          )}
          {answer && (
            <div className="analyst-answer">
              <span className="badge green-badge">{answer.label}</span>
              <h3>{answer.match}</h3>
              <p>{answer.answer}</p>
              <small>{answer.notice}</small>
            </div>
          )}
        </div>
        <p className="fine-print">
          AI uses verified match facts when available; data-backed answers stay
          available otherwise. Your question is sent to our AI provider for
          analysis. Sample mode uses sample data.
        </p>
      </div>
    </section>
  );
}
