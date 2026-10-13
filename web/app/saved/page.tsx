"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Selection, pct, stamp } from "@/lib/api";
import { useApp } from "@/components/shell";
import { Empty, ErrorBox, PredictionCard, Skeletons } from "@/components/ui";
type Saved = {
  id: string;
  saved_at: string;
  original: Selection;
  current: Selection | null;
};
export default function Page() {
  const { user } = useApp();
  const [items, setItems] = useState<Saved[] | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    if (user)
      api<{ items: Saved[] }>("/saved")
        .then((r) => setItems(r.items))
        .catch((e) => setError(e.message));
  }, [user]);
  async function remove(id: string) {
    try {
      await api("/saved/" + id, { method: "DELETE" });
      setItems((items) => items?.filter((s) => s.id !== id) || []);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="container section">
      <div className="page-heading">
        <div className="overline">YOUR SHORTLIST</div>
        <h1>Your saved picks.</h1>
        <p>Keep your favourite picks in one place.</p>
      </div>
      {!user ? (
        <Empty title="Sign in to save picks">
          <Link className="text-link" href="/account?next=/saved">
            Sign in or create an account →
          </Link>
        </Empty>
      ) : error ? (
        <ErrorBox message={error} />
      ) : items === null ? (
        <Skeletons />
      ) : !items.length ? (
        <Empty title="Your notebook starts here">
          <Link className="text-link" href="/predictions">
            Explore predictions and save a selection →
          </Link>
        </Empty>
      ) : (
        <div className="card-grid">
          {items.map((s) => (
            <div key={s.id}>
              <div className="saved-header">
                <span>
                  Saved {stamp(s.saved_at, user.preferences.timezone)}
                </span>
                <button className="text-button" onClick={() => remove(s.id)}>
                  Remove
                </button>
              </div>
              <PredictionCard s={s.original} oddsLabel="Saved odds" />
              <p className="saved-comparison">
                Current odds:{" "}
                {s.current
                  ? `${s.current.odds.toFixed(2)} decimal · ${pct(s.current.probability)} model chance`
                  : "Not available"}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
