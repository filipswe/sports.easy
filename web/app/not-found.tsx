import Link from "next/link";
export default function NotFound() {
  return (
    <div className="container section">
      <h1>This page is off the pitch.</h1>
      <p>The page or match could not be found.</p>
      <Link className="button primary" href="/predictions">
        Explore predictions
      </Link>
    </div>
  );
}
