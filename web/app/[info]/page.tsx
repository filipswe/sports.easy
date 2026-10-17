import Link from "next/link";
import { notFound } from "next/navigation";
const pages: Record<
  string,
  { title: string; intro: string; sections: { title: string; body: string }[] }
> = {
  "how-it-works": {
    title: "Understand the estimate.",
    intro:
      "An explainable baseline, with its assumptions in the open. Model version poisson-v1.1 is not validated to outperform bookmaker prices.",
    sections: [
      {
        title: "Historical goals → team strengths → score probabilities",
        body: "The baseline fits time-weighted Poisson regression with team attack, opponent defence and home advantage. L2 regularization shrinks small samples toward league strengths. Results have a 180-day half-life. A minimum of 40 league matches and 8 matches per team is required; otherwise the model abstains. Recent form only includes results available before the cutoff.",
      },
      {
        title: "One coherent score distribution",
        body: "1X2, over/under 2.5 and both-teams-to-score estimates come from the same independent home/away Poisson score grid. The grid extends until omitted tail mass is below 1e-12 per team and is normalized. Regulation time includes stoppage time and excludes extra time and penalties. Independence, stable team strengths and Poisson variance are assumptions that may fail.",
      },
      {
        title: "A price is not a probability",
        body: "Raw bookmaker implied probability is 1 / decimal odds. Model fair odds are 1 / estimated probability. Estimated EV per unit is probability × decimal odds − 1. At odds 2.00 and an estimate of 55%, implied probability is 50% and estimated EV is +10%. That does not establish that the estimate is correct. Failure probability is 1 − probability, not a complete measure of financial risk.",
      },
      {
        title: "Removing the margin, carefully",
        body: "No-vig probabilities are normalized only across a complete market from the same bookmaker, fixture, market line, regulation-time rules and source snapshot. Different bookmakers and incomplete groups are never combined for no-vig estimates.",
      },
      {
        title: "Data quality has published rules",
        body: "Insufficient: fewer than 40 available league results or 8 results for either team — no prediction is published. Limited: 8–19 results for either team, synthetic data, stale history/fixture feeds or stale/unknown quote timestamps. Good: at least 20 results for each team, sufficient league history, history and fixture fetches no older than 24 hours, and a source-dated quote no older than 10 minutes. This measures input coverage and freshness, not a validated confidence interval. Injuries, lineups, standings and xG are not used in this baseline.",
      },
      {
        title: "Likelihood labels have exact boundaries",
        body: "90–100%: Very high; 80–<90%: High; 70–<80%: Moderately high; 60–<70%: Above-even; 50–<60%: Slightly above-even; 40–<50%: Below-even; 30–<40%: Low; 0–<30%: Very low estimated likelihood. Each is an estimate, not a guarantee.",
      },
      {
        title: "Freshness is part of the result",
        body: "All supported markets use a 10-minute source-price threshold by default. Fetch time is shown separately from upstream update time; refreshing the site never refreshes upstream age. Missing source timestamps count as stale. Stale prices remain browsable but are excluded from fresh-only, positive-EV and current-EV rankings. Fixtures disappear from upcoming selections at kickoff or when the feed reports a non-scheduled state.",
      },
      {
        title: "Evaluation without hindsight",
        body: "The evaluator uses chronological 60/20/20 partitions and expanding past-only training in validation and test. Hyperparameters are fixed and calibration is not fitted. It reports binary outcome-averaged Brier score, log loss, calibration bins, sample sizes and a historical-frequency baseline by market. Results first fetched after a historical kickoff cannot be used as earlier training inputs. No historical bookmaker comparison or ROI is reported without synchronized historical prices.",
      },
      {
        title: "A record that can be inspected",
        body: "Quotes, predictions, publications and settlement revisions are append-only. Performance tracks the original publication attached to each official recommendation, once per fixture. Hypothetical returns use one unit per settled record at its original price, with pending, void and postponed records excluded. These correlated records do not represent an executable betting strategy. Corrections create additional settlement revisions.",
      },
      {
        title: "Explanations, without invented facts",
        body: "The MVP uses a deterministic explanation built from model factors and missing-input labels. Optional AI recognizes the requested game and pick; displayed answers use stored facts and prices. It does not invent probabilities.",
      },
    ],
  },
  about: {
    title: "A clearer way to research football.",
    intro:
      "sports.easy is a football prediction and match analysis application. “Betting made easy” is the brand slogan, not a promise of easy winnings.",
    sections: [
      {
        title: "Small scope. Inspectable decisions.",
        body: "The app covers the top five leagues and upcoming European competitions, with offered 1X2, BTTS, double-chance and full-time/first-half goal prices. The application does not place bets, accept money or connect to bookmaker accounts.",
      },
      {
        title: "Original by design",
        body: "The interface uses a simple original pitch illustration, a text-based logo and club crests to identify teams. Team names provide context; no official league or club affiliation is implied.",
      },
    ],
  },
  privacy: {
    title: "Privacy, in plain language.",
    intro:
      "Draft policy for local use. The operator must supply contact details, retention periods and jurisdiction-specific terms before public release.",
    sections: [
      {
        title: "What is stored",
        body: "Accounts store an email address, Argon2 password hash, verification status, preferences, session references and saved research links. Public request limits store short-lived keyed network-address digests without raw IP addresses. These counters expire after two minutes and are removed on a subsequent successful window reservation or worker cleanup. Provider keys remain server-side. No payment, bookmaker-account or gambling transaction information is collected.",
      },
      {
        title: "Cookies and retention",
        body: "One HttpOnly, SameSite=Lax session cookie supports authentication and request verification. Sessions expire after seven days. Reset and verification links expire after 30 minutes and can only be used once. No analytics or advertising cookies are configured. Expired session/token cleanup runs through the worker.",
      },
      {
        title: "Deletion",
        body: "The current analyst question, up to two previous questions and a bounded list of upcoming match names/kickoffs are sent to Groq when the optional AI service is enabled. Chat text is not stored by this application; provider processing follows its own policy. Shared quota counters expire after two days and are removed by the worker or a subsequent successful chat request. Account settings allow deletion after password confirmation. This removes the user, preferences, sessions, reset tokens and saved selections. Anonymous published prediction and settlement records remain for research integrity. Backup expiry and provider retention must be configured by the deployment operator.",
      },
    ],
  },
  terms: {
    title: "Terms of research use.",
    intro:
      "Draft terms requiring jurisdiction-specific legal review before commercial release. This local portfolio application is intended for adults aged 18 and older.",
    sections: [
      {
        title: "Estimates and availability",
        body: "Information is supplied for research. Probabilities may be inaccurate, prices may be stale or unavailable, and no return is guaranteed. A recorded bookmaker quote does not prove that it could have been accepted. Demo fixtures, prices, historical results and evaluations are synthetic.",
      },
      {
        title: "Scope of service",
        body: "Saved selections are research records, not placed bets. There are no deposits, wallets, subscriptions, affiliate links, automated wagers or bookmaker-account integrations. You are responsible for checking the rules applicable in your location.",
      },
      {
        title: "Before public operation",
        body: "An operator must confirm data display and retention rights, privacy and consumer obligations, required notices and age-access requirements for the intended jurisdiction. This draft does not establish legal compliance.",
      },
    ],
  },
  "responsible-use": {
    title: "Research should stay in perspective.",
    intro:
      "For adults 18 and older. Football outcomes are uncertain. No selection is guaranteed and no model removes the possibility of loss.",
    sections: [
      {
        title: "Understand the limits",
        body: "Short odds do not make an outcome certain. Estimated EV depends on the quality of a probability estimate. Data-quality labels do not measure every source of uncertainty or financial risk.",
      },
      {
        title: "Keep decisions your own",
        body: "Do not treat this portfolio demonstration as financial advice or a reason to wager. Never chase losses or use money needed for essential expenses. Take a break if research or gambling is causing distress, and seek appropriate local support.",
      },
      {
        title: "A research-only product",
        body: "sports.easy has no staking prompts, payment features or bet placement. Regional notices are configurable; actual jurisdiction-specific requirements need review before public use.",
      },
    ],
  },
};
export async function generateMetadata({
  params,
}: {
  params: Promise<{ info: string }>;
}) {
  const { info } = await params;
  return { title: pages[info]?.title || "Page not found" };
}
export default async function Page({
  params,
}: {
  params: Promise<{ info: string }>;
}) {
  const { info } = await params;
  const page = pages[info];
  if (!page) notFound();
  if (info === "how-it-works")
    return (
      <article className="container section how-page">
        <div className="page-heading">
          <div className="overline">LESS GUESSWORK. MORE FOOTBALL.</div>
          <h1>
            Good picks start with
            <br />a clearer picture.
          </h1>
          <p>
            Find a match, understand your pick, and put your ideas together.
          </p>
        </div>
        <div className="steps">
          {[
            [
              "01",
              "Find your match",
              "Browse upcoming fixtures or start with our recommended picks. The shortlist highlights our highest estimated chances, with one pick per match.",
            ],
            [
              "02",
              "See what the numbers say",
              "Open a match for recent form, results and goal stats. Choose a market to see the model’s estimated chance of your pick winning.",
            ],
            [
              "03",
              "Build your parlay",
              "Add picks from different matches. Your parlay shows combined odds and the chance of every pick winning. Save it to revisit later.",
            ],
          ].map(([n, title, body]) => (
            <section className="step" key={n}>
              <span className="step-number">{n}</span>
              <h2>{title}</h2>
              <p>{body}</p>
            </section>
          ))}
        </div>
        <section className="how-example panel">
          <div>
            <h2>What does a 60% chance mean?</h2>
            <p>
              For similar situations, the model expects that outcome about 6
              times in 10. It still expects it to lose about 4 times in 10.
            </p>
            <p>
              Adding more picks lowers the chance of them all winning. Three
              independent picks with a 60% chance each combine to about a 22%
              chance.
            </p>
          </div>
          <div className="chance-example" aria-label="Six of ten outcomes">
            <div>
              {Array.from({ length: 10 }, (_, i) => (
                <span className={i < 6 ? "hit" : ""} key={i} />
              ))}
            </div>
            <strong>
              60<span>%</span>
            </strong>
            <p>An estimate. Never a promise.</p>
          </div>
        </section>
        <section className="faq-simple">
          <h2>A few things to know</h2>
          {[
            [
              "How are the recommended picks chosen?",
              "We choose up to five picks for the soonest matchday across European competitions and the top five leagues. We use match history when supported, and a labelled market-based estimate from real prices when history is missing. The pick and price are saved before kickoff so you can follow their results on Performance.",
            ],
            [
              "Can I choose my own picks?",
              "Yes. Browse All matches, select the outcome you want and open the match analysis. Add one pick per match to your parlay; the app calculates the combined chance. You can enter your own decimal odds if a market has no quoted price.",
            ],
            [
              "Where do the odds come from?",
              "The app uses one configured sportsbook feed. Until live providers are connected, fixtures, results and odds are clearly labelled as sample data. Missing prices are shown as a dash.",
            ],
            [
              "Can I place a bet here?",
              "No. sports.easy helps you analyze and save picks. It does not accept money or place bets.",
            ],
            [
              "What does the model consider?",
              "Past scores, opponent strength, home advantage and recent results. It does not currently account for injuries or confirmed lineups. Those can change a match, so use the estimates as one part of your decision.",
            ],
          ].map(([title, body]) => (
            <details key={title}>
              <summary>{title}</summary>
              <p>{body}</p>
            </details>
          ))}
        </section>
        <div className="hero-actions">
          <Link href="/predictions" className="button primary">
            Explore matches →
          </Link>
          <Link href="/performance" className="button secondary">
            See our record
          </Link>
        </div>
        <details className="method-details">
          <summary>The model & methodology in detail</summary>
          {page.sections.map((s) => (
            <section key={s.title}>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </section>
          ))}
        </details>
      </article>
    );
  return (
    <article className="container section prose">
      <div className="overline">SPORTS.EASY / OPEN BY DESIGN</div>
      <h1>{page.title}</h1>
      <p>{page.intro}</p>
      {page.sections.map((s) => (
        <section key={s.title}>
          <h2>{s.title}</h2>
          <p>{s.body}</p>
        </section>
      ))}
    </article>
  );
}
