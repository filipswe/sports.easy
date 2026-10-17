"""Conservative club-name folding; no fuzzy identity matching for provider data."""

import re
import unicodedata


def normalized_name(value):
    value = value.casefold().replace("ø", "o").replace("ł", "l").replace("đ", "d")
    value = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z0-9]+", value))
