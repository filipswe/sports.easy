"use client";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowUpRight, Bookmark, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "./shell";
import { ErrorBox } from "./ui";
export function Account() {
  const { user, refresh, meta } = useApp(),
    params = useSearchParams();
  const [mode, setMode] = useState("login"),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [link, setLink] = useState("");
  const [timezone, setTimezone] = useState("Europe/Belgrade"),
    [oddsFormat, setOddsFormat] = useState("decimal"),
    [league, setLeague] = useState(""),
    [filters, setFilters] = useState("");
  const token = params.get("verify") || params.get("reset");
  useEffect(() => {
    if (params.has("verify")) setMode("verify");
    else if (params.has("reset")) setMode("reset");
  }, [params]);
  useEffect(() => {
    if (user) {
      setTimezone(
        user.preferences.timezone ||
          Intl.DateTimeFormat().resolvedOptions().timeZone,
      );
      setOddsFormat(user.preferences.odds_format || "decimal");
      setLeague(user.preferences.leagues?.[0] || "");
      setFilters(user.preferences.filters || "");
    }
  }, [user]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    setLink("");
    try {
      const endpoint = mode === "forgot" ? "request-reset" : mode;
      const body =
        mode === "verify"
          ? { token }
          : mode === "reset"
            ? { token, password }
            : mode === "forgot"
              ? { email }
              : { email, password };
      const result = await api<{ message?: string; demo_link?: string }>(
        "/auth/" + endpoint,
        { method: "POST", body: JSON.stringify(body) },
      );
      setMessage(result.message || "Signed in.");
      if (result.demo_link) setLink(result.demo_link);
      if (mode === "login") {
        refresh();
        const next = params.get("next");
        if (next && next.startsWith("/") && !next.startsWith("//"))
          window.location.href = next;
      }
      if (mode === "reset" || mode === "verify") setMode("login");
      setPassword("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function preferences(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/preferences", {
        method: "PUT",
        body: JSON.stringify({
          timezone,
          odds_format: oddsFormat,
          leagues: league ? [league] : [],
          filters,
        }),
      });
      refresh();
      setMessage("Preferences saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    await api("/auth/logout", { method: "POST" });
    refresh();
    setMessage("Signed out.");
  }
  async function deleteAccount(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/auth/account", {
        method: "DELETE",
        body: JSON.stringify({ password }),
      });
      refresh();
      setPassword("");
      setMessage("Account and personal research records deleted.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="container auth-layout">
      <div className="auth-copy">
        <div className="overline">YOUR SPORTS.EASY ACCOUNT</div>
        <h1>
          Keep the context.
          <br />
          <span className="green">Keep your favourites.</span>
        </h1>
        <p>
          Return to the exact price and model version you researched, even after
          the data moves on.
        </p>
        <div className="notice">
          <Bookmark size={19} />
          <span>
            Saved selections are personal research records. They are never
            placed bets.
          </span>
        </div>
        <p>
          <ShieldCheck
            size={17}
            style={{ display: "inline", marginRight: 7 }}
          />
          Browse freely. An account is only needed to save research.
        </p>
        {meta?.email_demo && (
          <p className="hint">
            Local demo email mode: verification and reset links appear here
            instead of being sent. Use a fictional address and a unique test
            password. This mode must not be publicly deployed.
          </p>
        )}
      </div>
      <div>
        <div className="auth-panel">
          {user ? (
            <>
              <h2>Your account</h2>
              <p>{user.email}</p>
              <form onSubmit={preferences}>
                <label>
                  Display timezone
                  <input
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    placeholder="Europe/Belgrade"
                    required
                  />
                </label>
                <label>
                  Odds format
                  <select
                    value={oddsFormat}
                    onChange={(e) => setOddsFormat(e.target.value)}
                  >
                    <option value="decimal">Decimal</option>
                    <option value="american">American</option>
                  </select>
                </label>
                <label>
                  Preferred competition
                  <select
                    value={league}
                    onChange={(e) => setLeague(e.target.value)}
                  >
                    <option value="">All supported</option>
                    {meta?.leagues.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name} · {l.season}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Saved filter query
                  <input
                    value={filters}
                    onChange={(e) => setFilters(e.target.value)}
                    placeholder="min_odds=1.75&max_odds=3"
                    maxLength={2000}
                  />
                </label>
                <button className="button primary full" disabled={busy}>
                  Save preferences
                </button>
              </form>
              <div style={{ display: "flex", gap: 15, marginTop: 18 }}>
                <Link
                  href={"/research?" + (filters || "")}
                  className="text-link"
                >
                  Open saved filters
                </Link>
                <button onClick={logout} className="text-button">
                  Sign out
                </button>
              </div>
              {user.admin && (
                <Link className="text-link" href="/admin">
                  Ingestion admin <ArrowUpRight size={15} />
                </Link>
              )}
              <details style={{ marginTop: 22 }}>
                <summary className="danger">
                  Delete account and saved research
                </summary>
                <form onSubmit={deleteAccount}>
                  <p className="hint">
                    This permanently removes your account, sessions, preferences
                    and saved selections. Anonymous publication records remain.
                  </p>
                  <label style={{ marginTop: 15 }}>
                    Confirm password
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="current-password"
                      required
                    />
                  </label>
                  <button
                    disabled={busy}
                    className="button secondary danger full"
                  >
                    Permanently delete my account
                  </button>
                </form>
              </details>
            </>
          ) : (
            <>
              <div className="tabs">
                {[
                  ["login", "Sign in"],
                  ["register", "Create account"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => {
                      setMode(value);
                      setError("");
                      setMessage("");
                      setLink("");
                    }}
                    className={mode === value ? "active" : ""}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <h2>
                {
                  {
                    login: "Welcome back.",
                    register: "Your picks, in one place.",
                    forgot: "Reset your password.",
                    verify: "Verify your email.",
                    reset: "Choose a new password.",
                  }[mode]
                }
              </h2>
              <form onSubmit={submit}>
                {!["verify", "reset"].includes(mode) && (
                  <label>
                    Email address
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                      required
                    />
                  </label>
                )}
                {!["verify", "forgot"].includes(mode) && (
                  <label>
                    Password
                    <input
                      type="password"
                      minLength={12}
                      maxLength={128}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete={
                        mode === "login" ? "current-password" : "new-password"
                      }
                      required
                    />
                    <span className="hint">At least 12 characters.</span>
                  </label>
                )}
                {mode === "register" && (
                  <label className="checkbox">
                    <input type="checkbox" required />I am 18 or older and have
                    read the Terms.
                  </label>
                )}
                <button disabled={busy} className="button primary full">
                  {busy
                    ? "Working…"
                    : {
                        login: "Sign in",
                        register: "Create account",
                        forgot: "Send reset link",
                        verify: "Verify email",
                        reset: "Update password",
                      }[mode]}
                  <ArrowUpRight size={16} />
                </button>
              </form>
              {mode === "login" && (
                <button
                  className="text-button full"
                  onClick={() => setMode("forgot")}
                >
                  Forgot password?
                </button>
              )}
            </>
          )}
          {error && <ErrorBox message={error} />}
          <div aria-live="polite">
            {message && <div className="notice">{message}</div>}
            {link && (
              <div className="notice amber">
                <div>
                  <strong>Local demo email</strong>
                  <br />
                  <a className="text-link" href={link}>
                    Open verification / reset link →
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
