# Club crest assets

Real provider PNGs are cached here so the shared team badge does not depend on a remote image request for known clubs. The catalogs cover all 171 teams present in the live beta database on 14 October 2026, seven additional clubs reviewed on 17 October, and existing reviewed/demo club names. All 180 team records in the refreshed local live cache resolve to a reviewed crest.

`backend/app/club_crests.json` records each reviewed name, provider identity, source URL and local asset. `web/lib/clubs.json` maps every reviewed name to that same asset and retains existing aliases. Sources are the recorded `crests.football-data.org` and `media.api-sports.io` URLs; Additional bookmaker aliases were checked against provider country/name records and primary UEFA identity references recorded as `identity_source`; no club identity was guessed and no synthetic logos were generated.

PNG signatures, dimensions and full image decoding were checked when retrieving the assets. Backend tests require both catalogs to agree and every cached file to exist. Shared UI badges try the cache first, then a supplied provider URL, then initials if both fail. Newly encountered clubs can still use the worker's bounded provider lookup; their cached catalog entry must be reviewed separately.

The operator confirmed the required club-logo permissions for this beta. The images remain the property of their respective owners; a provider key alone does not grant those rights.
