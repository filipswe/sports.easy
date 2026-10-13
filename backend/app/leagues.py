"""The five supported domestic leagues, with explicit provider identifiers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class League:
    id: int
    name: str
    sport: str
    clubs: tuple[tuple[str, int], ...]


LEAGUES = (
    League(
        39,
        "Premier League",
        "soccer_epl",
        (
            ("Arsenal", 42),
            ("Chelsea", 49),
            ("Liverpool", 40),
            ("Manchester City", 50),
            ("Newcastle United", 34),
            ("Aston Villa", 66),
            ("Tottenham Hotspur", 47),
            ("Brighton", 51),
            ("Manchester United", 33),
            ("Everton", 45),
            ("Fulham", 36),
            ("Brentford", 55),
        ),
    ),
    League(
        140,
        "La Liga",
        "soccer_spain_la_liga",
        (
            ("Real Madrid", 541),
            ("Barcelona", 529),
            ("Atletico Madrid", 530),
            ("Athletic Club", 531),
            ("Real Sociedad", 548),
            ("Villarreal", 533),
            ("Real Betis", 543),
            ("Valencia", 532),
            ("Sevilla", 536),
            ("Girona", 547),
            ("Osasuna", 727),
            ("Getafe", 546),
        ),
    ),
    League(
        135,
        "Serie A",
        "soccer_italy_serie_a",
        (
            ("Inter", 505),
            ("AC Milan", 489),
            ("Juventus", 496),
            ("Napoli", 492),
            ("Roma", 497),
            ("Lazio", 487),
            ("Atalanta", 499),
            ("Fiorentina", 502),
            ("Bologna", 500),
            ("Torino", 503),
            ("Udinese", 494),
            ("Genoa", 495),
        ),
    ),
    League(
        78,
        "Bundesliga",
        "soccer_germany_bundesliga",
        (
            ("Bayern Munich", 157),
            ("Borussia Dortmund", 165),
            ("Bayer Leverkusen", 168),
            ("RB Leipzig", 173),
            ("Eintracht Frankfurt", 169),
            ("Stuttgart", 172),
            ("Freiburg", 160),
            ("Werder Bremen", 162),
            ("Wolfsburg", 161),
            ("Borussia Monchengladbach", 163),
            ("Mainz", 164),
            ("Augsburg", 170),
        ),
    ),
    League(
        61,
        "Ligue 1",
        "soccer_france_ligue_one",
        (
            ("Paris Saint-Germain", 85),
            ("Marseille", 81),
            ("Monaco", 91),
            ("Lyon", 80),
            ("Lille", 79),
            ("Nice", 84),
            ("Lens", 116),
            ("Rennes", 94),
            ("Strasbourg", 95),
            ("Nantes", 83),
            ("Toulouse", 96),
            ("Brest", 106),
        ),
    ),
)
BY_ID = {league.id: league for league in LEAGUES}
BY_SPORT = {league.sport: league for league in LEAGUES}
CLUBS = {name: name.lower().replace(" ", "-") for league in LEAGUES for name, _ in league.clubs}


def fixture_league(fixture):
    """Competition IDs encode provider league and season, independently of display names."""
    try:
        return BY_ID.get(int(fixture.provider_id.split(":")[1]))
    except (ValueError, IndexError):
        return None
