"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bookmark,
  Menu,
  X,
  Layers3,
} from "lucide-react";
import { api, Meta, User } from "@/lib/api";
import { useParlay } from "./parlay-context";
const Context = createContext<{
  meta: Meta | null;
  user: User | null;
  refresh: () => void;
}>({ meta: null, user: null, refresh: () => {} });
export const useApp = () => useContext(Context);
const links = [
  ["/", "Home"],
  ["/predictions", "All matches"],
  ["/parlays", "Parlays"],
  ["/performance", "Performance"],
  ["/how-it-works", "How it works"],
];
export function Shell({ children }: { children: React.ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null),
    [user, setUser] = useState<User | null>(null),
    [open, setOpen] = useState(false),
    [failed, setFailed] = useState(false);
  const path = usePathname(),
    { picks, message } = useParlay();
  function refresh() {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }
  useEffect(() => {
    api<Meta>("/meta")
      .then(setMeta)
      .catch(() => setFailed(true));
    refresh();
  }, []);
  return (
    <Context.Provider value={{ meta, user, refresh }}>
      <a href="#main" className="skip">
        Skip to content
      </a>
      <header>
        <div className="nav-wrap">
          <Link href="/" className="logo" aria-label="sports.easy home">
            <span className="logo-icon">
              <Activity size={22} />
            </span>
            sports<span>.easy</span>
          </Link>
          <nav
            className={open ? "nav open" : "nav"}
            aria-label="Main navigation"
          >
            {links.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={path === href ? "active" : ""}
              >
                {label}
              </Link>
            ))}
          </nav>
          <div className="nav-actions">
            <Link
              href="/saved"
              className="icon-button"
              aria-label="Saved picks"
            >
              <Bookmark size={19} />
            </Link>
            <Link href="/account" className="account-link">
              {user ? "My account" : "Sign in"}
              <ArrowUpRight size={14} />
            </Link>
            <button
              className="mobile-menu icon-button"
              onClick={() => setOpen(!open)}
              aria-expanded={open}
              aria-label="Toggle navigation"
            >
              {open ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>
      <div className="app-status">
        <div className="container">
          <span>
            <span className="status-dot" />
            Football, a little clearer.
          </span>
          <span>
            {meta?.mode === "demo"
              ? "Sample data · Live feed not connected"
              : meta
                ? "Current odds"
                : failed
                  ? "Data service unavailable"
                  : "Connecting…"}
          </span>
        </div>
      </div>
      <main id="main">{children}</main>
      <div
        className={
          message.startsWith("Choose") || message.startsWith("A parlay")
            ? "parlay-feedback"
            : "sr-only"
        }
        role="status"
      >
        {message}
      </div>
      {picks.length > 0 && path !== "/parlays" && (
        <Link className="floating-slip" href="/parlays">
          <Layers3 size={18} /> My parlay <b>{picks.length}</b>
          <ArrowUpRight size={18} />
        </Link>
      )}
      <footer>
        <div>
          <Link className="logo" href="/">
            sports<span>.easy</span>
          </Link>
          <p>Your matchday, made simpler.</p>
          {meta?.mode === "live" &&
            meta.football_provider === "football-data" && (
              <p>
                Football data provided by the{" "}
                <a href="https://www.football-data.org/">
                  Football-Data.org API
                </a>
                .
              </p>
            )}
        </div>
        <div className="footer-links">
          {[
            ["/about", "About"],
            ["/privacy", "Privacy"],
            ["/terms", "Terms"],
            ["/responsible-use", "Responsible use"],
          ].map(([href, label]) => (
            <Link href={href} key={href}>
              {label}
            </Link>
          ))}
        </div>
        <div className="footer-note">
          <b>18+ · Every pick has a chance of losing.</b>
          <p>Estimates, not guarantees. Prices can change.</p>
          <span>© {new Date().getFullYear()} sports.easy</span>
        </div>
      </footer>
    </Context.Provider>
  );
}
