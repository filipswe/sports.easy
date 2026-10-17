"use client";

import { useState, type FormEvent } from "react";
import { ArrowUpRight, MessageCircle, Send } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

type Answer = {
  label: string;
  answer: string;
  notice: string;
  match: string | null;
  fixture_id: string | null;
};

export function AnalystChat() {
  const [context, setContext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || question.trim().length < 2) return;
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      const result = await api<Answer>("/chat", {
        method: "POST",
        body: JSON.stringify({
          question: question.trim(),
          context_fixture_id: context,
          previous_questions: previous,
        }),
      });
      setAnswer(result);
      setContext(result.fixture_id);
      setPrevious((questions) => [...questions, question.trim()].slice(-2));
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
          Ask about a team, a match or a pick in your own words. Get current
          prices, recent form and the reasons behind the model’s view.
        </p>
        <Link href="/parlays" className="text-link">
          Ready to combine your picks? <ArrowUpRight size={16} />
        </Link>
      </div>
      <div className="analyst-card panel">
        <form onSubmit={ask}>
          <label htmlFor="analyst-question">What would you like to know?</label>
          <textarea
            id="analyst-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={600}
            minLength={2}
            rows={3}
            required
            placeholder="What do you think of Arsenal to win their next game?"
            disabled={busy}
          />
          <div className="analyst-prompts">
            {[
              ...(context
                ? [
                    "Why does the model favor this pick?",
                    "What is the recent form?",
                    "What are the current odds?",
                  ]
                : [
                    "What are the odds for Arsenal’s next game?",
                    "Explain BTTS",
                    "What should I consider for a parlay?",
                  ]),
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
            disabled={busy || question.trim().length < 2}
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
              {answer.match && (
                <Link
                  href={`/matches/${answer.fixture_id}`}
                  className="text-link"
                >
                  {answer.match} <ArrowUpRight size={15} />
                </Link>
              )}
              <p>{answer.answer}</p>
              <small>{answer.notice}</small>
            </div>
          )}
        </div>
        <p className="fine-print">
          AI uses verified match facts when available; data-backed answers stay
          available otherwise. Your question and up to two previous questions
          are sent to our AI provider to understand the match and topic. Sample
          mode uses sample data.
        </p>
      </div>
    </section>
  );
}
