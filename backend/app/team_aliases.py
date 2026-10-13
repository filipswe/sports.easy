"""Exact Pinnacle names reviewed against football-data.org club IDs on 2026-10-13.

These are explicit identities, never fuzzy name matches. New/unlisted names abstain.
"""

from sqlalchemy import select

from .models import ProviderMapping, Team
from .providers import ProviderUnavailable

FOOTBALL_DATA_ODDS_ALIASES = {
    # Premier League
    65: "Manchester City",
    66: "Manchester United",
    67: "Newcastle United",
    73: "Tottenham Hotspur",
    351: "Nottingham Forest",
    397: "Brighton and Hove Albion",
    # La Liga
    77: "Athletic Bilbao",
    78: "Atlético Madrid",
    79: "CA Osasuna",
    81: "Barcelona",
    285: "Elche CF",
    558: "Celta Vigo",
    559: "Sevilla",
    560: "Deportivo La Coruña",
    5335: "Real Racing Club de Santander",
    # Serie A
    98: "AC Milan",
    100: "AS Roma",
    102: "Atalanta BC",
    108: "Inter Milan",
    454: "Venezia",
    7397: "Como",
    # Bundesliga
    2: "TSG Hoffenheim",
    3: "Bayer Leverkusen",
    4: "Borussia Dortmund",
    5: "Bayern Munich",
    6: "FC Schalke 04",
    7: "Hamburger SV",
    10: "VfB Stuttgart",
    12: "Werder Bremen",
    15: "FSV Mainz 05",
    17: "SC Freiburg",
    18: "Borussia Monchengladbach",
    19: "Eintracht Frankfurt",
    # Ligue 1
    523: "Lyon",
    524: "Paris Saint Germain",
    529: "Rennes",
    532: "Angers",
    535: "Le Mans FC",
    548: "AS Monaco",
}


def install_football_data_aliases(db):
    teams = {t.provider_id: t for t in db.scalars(select(Team))}
    installed = 0
    for source_id, name in FOOTBALL_DATA_ODDS_ALIASES.items():
        team = teams.get(f"football-data:{source_id}")
        if not team:
            continue
        existing = db.scalar(
            select(ProviderMapping).where(
                ProviderMapping.provider == "the-odds-api",
                ProviderMapping.entity_type == "team",
                ProviderMapping.external_id == name,
            )
        )
        if existing:
            if existing.entity_id != team.id:
                raise ProviderUnavailable(
                    "Reviewed bookmaker club alias conflicts with existing identity"
                )
            continue
        db.add(
            ProviderMapping(
                provider="the-odds-api",
                entity_type="team",
                external_id=name,
                entity_id=team.id,
            )
        )
        installed += 1
    db.flush()
    return installed
