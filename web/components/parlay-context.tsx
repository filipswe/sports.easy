"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { Pick, pickKey } from "@/lib/matchday";
const Context = createContext<{
  picks: Pick[];
  toggle: (p: Pick) => void;
  replace: (p: Pick[]) => void;
  remove: (id: string) => void;
  clear: () => void;
  message: string;
}>({
  picks: [],
  toggle: () => {},
  replace: () => {},
  remove: () => {},
  clear: () => {},
  message: "",
});
export const useParlay = () => useContext(Context);
export function ParlayProvider({ children }: { children: React.ReactNode }) {
  const [picks, setPicks] = useState<Pick[]>([]),
    [ready, setReady] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("sports-easy-parlay") || "[]",
      );
      if (Array.isArray(saved))
        setPicks(
          saved
            .filter(
              (p) =>
                p &&
                typeof p.fixture_id === "string" &&
                typeof p.market === "string" &&
                typeof p.outcome === "string" &&
                typeof p.home === "string" &&
                typeof p.away === "string",
            )
            .slice(0, 8),
        );
    } catch {
      // Storage may be disabled; the current session still works.
    }
    setReady(true);
  }, []);
  useEffect(() => {
    if (ready)
      try {
        localStorage.setItem("sports-easy-parlay", JSON.stringify(picks));
      } catch {
        // Storage may be disabled; the current session still works.
      }
  }, [picks, ready]);
  function toggle(p: Pick) {
    if (picks.some((x) => pickKey(x) === pickKey(p))) {
      setPicks(picks.filter((x) => pickKey(x) !== pickKey(p)));
      setMessage("Pick removed");
      return;
    }
    const existing = picks.find((x) => x.fixture_id === p.fixture_id);
    if (!existing && picks.length >= 8) {
      setMessage("A parlay can contain up to 8 matches.");
      return;
    }
    if (
      picks.some(
        (x) =>
          x.fixture_id !== p.fixture_id &&
          [x.home, x.away].some((t) => t === p.home || t === p.away),
      )
    ) {
      setMessage("Choose matches with different clubs for this parlay.");
      return;
    }
    setPicks([...picks.filter((x) => x.fixture_id !== p.fixture_id), p]);
    setMessage(
      existing ? "Updated your pick for this match" : "Added to your parlay",
    );
  }
  return (
    <Context.Provider
      value={{
        picks,
        toggle,
        replace: (p) => {
          setPicks(p);
          setMessage("Parlay loaded");
        },
        remove: (id) => setPicks(picks.filter((p) => pickKey(p) !== id)),
        clear: () => setPicks([]),
        message,
      }}
    >
      {children}
    </Context.Provider>
  );
}
