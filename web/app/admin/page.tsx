"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorBox } from "@/components/ui";
export default function Page() {
  const [data, setData] = useState<unknown>(null),
    [error, setError] = useState("");
  useEffect(() => {
    api("/admin/status")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <div className="container section">
      <div className="overline">OPERATIONS · PROTECTED</div>
      <h1>Ingestion status</h1>
      {error ? (
        <ErrorBox message={error} />
      ) : (
        <div className="panel">
          <h2>Provider health, quota and jobs</h2>
          <p>
            Credentials are represented only as present / absent. No provider
            secrets are displayed.
          </p>
          <pre>{data ? JSON.stringify(data, null, 2) : "Loading…"}</pre>
        </div>
      )}
    </div>
  );
}
