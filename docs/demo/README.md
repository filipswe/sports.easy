# Portfolio demonstration

Recorded on 17 October 2026 from code revision `a7e796a` (the UI is unchanged by that revision's PostgreSQL lock fix). The isolated preview used real cached provider fixtures/prices, local SQLite, reviewed crests and optional grounded chat. This is a point-in-time recording, not a promise that these fixtures or prices remain current.

[Watch the walkthrough](walkthrough.webm). Download it if your Markdown viewer does not play WebM. It shows Home, chronological matches, goal-line selection, match analysis, a three-match parlay, save/reload, Performance and a free-form analysis question. Loading states during navigation are real. No private account credentials or email tokens are included.

| View | Screenshot |
|---|---|
| Home | [Desktop](home-desktop.png) / [390px mobile](home-mobile.png) |
| All matches | [Desktop](matches-desktop.png) |
| Match analysis | [Desktop](analysis-desktop.png) |
| Parlay builder | [Desktop](parlay-desktop.png) |
| Official-pick Performance | [Desktop](performance-desktop.png) |

The capture checked 85 priced matches in kickoff order, all 170 visible club images loaded, three selections from different matches, parlay save/reload, the official archive, an analysis answer and no mobile horizontal overflow or browser JavaScript errors. The recommendations show only the earliest upcoming calendar matchday; fewer than five is valid when fewer priced matches remain. Performance in this local database is separate from the hosted archive. Neither sample establishes predictive accuracy.

To reproduce from this prepared checkout:

```sh
.venv/bin/python scripts/preview.py --live --ai
```

Keep the terminal running and open http://127.0.0.1:3101. This uses private ignored project credentials and a separate cached database under `.preview/`. Cached coverage changes as events start and results arrive. Use `scripts/preview.py` without flags for a new labelled sample-data preview without provider credentials. For a fresh clone, follow the Docker Compose quick start in the [README](../../README.md).

Use the manual operator refresh described in the README for the hosted database. Do not reset a real database to reproduce a screenshot, edit original picks after seeing results, fabricate missing quotes, or run multiple refreshers against a free provider account.
