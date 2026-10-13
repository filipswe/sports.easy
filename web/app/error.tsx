"use client";
export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="container section">
      <h1>We couldn’t load this view.</h1>
      <p>
        Your saved records remain in the database. Try again when the service is
        available.
      </p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
