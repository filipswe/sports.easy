"""Only display club assets from the configured football providers."""

from urllib.parse import urlsplit

from .leagues import CLUBS


def safe_crest(value):
    if not isinstance(value, str) or len(value) > 300:
        return None
    try:
        url = urlsplit(value)
        valid = (
            url.scheme == "https"
            and url.hostname in {"crests.football-data.org", "media.api-sports.io"}
            and not url.username
            and not url.password
            and url.port is None
            and not url.query
            and not url.fragment
            and url.path.lower().endswith((".png", ".svg", ".webp"))
        )
        return value if valid else None
    except ValueError:
        return None


def team_logo(team):
    source = safe_crest(team.crest_url)
    if source:
        return source
    if team.name in CLUBS:
        return "/clubs/" + CLUBS[team.name] + ".png"
    provider_id = team.provider_id.removeprefix("api-football:")
    if provider_id.isdigit():
        return f"https://media.api-sports.io/football/teams/{provider_id}.png"
    return None
