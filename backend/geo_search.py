"""Geo & search helpers — strict company match (accent-insensitive),
Haversine distance, French city geocoding, EU country detection.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Optional, Tuple


# ---------- Normalization ----------
def normalize_text(s: Optional[str]) -> str:
    """Lowercase + remove diacritics + strip + collapse whitespace + remove common suffixes.
    E.g. "EDF S.A." → "edf sa" ; "Crédit Agricole" → "credit agricole"
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Remove punctuation
    s = re.sub(r"[.,;:()\[\]'\"’]", " ", s)
    # Remove common French/intl. company suffixes
    s = re.sub(
        r"\b(sa|sas|sasu|sarl|eurl|sci|sci|sa de cv|ag|gmbh|llc|inc|ltd|corp|company|co|group|groupe|holding|s a r l)\b",
        " ",
        s,
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s


def companies_match(a: Optional[str], b: Optional[str]) -> bool:
    """Strict match (after normalization)."""
    if not a or not b:
        return False
    return normalize_text(a) == normalize_text(b)


def company_contains_term(name: Optional[str], term: Optional[str]) -> bool:
    """For autocomplete-style match: term must appear as a whole word inside name."""
    if not name or not term:
        return False
    norm_name = normalize_text(name)
    norm_term = normalize_text(term)
    if not norm_term:
        return False
    return re.search(rf"\b{re.escape(norm_term)}\b", norm_name) is not None


# ---------- Haversine ----------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------- French city geocoding (top ~120 cities) ----------
# Source: INSEE / Wikipedia approximate coordinates
FR_CITIES: dict[str, Tuple[float, float]] = {
    "paris": (48.8566, 2.3522),
    "marseille": (43.2965, 5.3698),
    "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442),
    "nice": (43.7102, 7.2620),
    "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521),
    "montpellier": (43.6109, 3.8772),
    "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573),
    "rennes": (48.1173, -1.6778),
    "reims": (49.2583, 4.0317),
    "toulon": (43.1242, 5.9280),
    "saint-etienne": (45.4397, 4.3872),
    "le havre": (49.4944, 0.1079),
    "grenoble": (45.1885, 5.7245),
    "dijon": (47.3220, 5.0415),
    "angers": (47.4784, -0.5632),
    "villeurbanne": (45.7665, 4.8795),
    "saint-denis": (48.9362, 2.3574),
    "le mans": (48.0061, 0.1996),
    "aix-en-provence": (43.5297, 5.4474),
    "brest": (48.3905, -4.4861),
    "nimes": (43.8367, 4.3601),
    "limoges": (45.8336, 1.2611),
    "clermont-ferrand": (45.7772, 3.0870),
    "tours": (47.3941, 0.6848),
    "amiens": (49.8941, 2.2958),
    "perpignan": (42.6886, 2.8946),
    "metz": (49.1193, 6.1757),
    "besancon": (47.2378, 6.0241),
    "boulogne-billancourt": (48.8358, 2.2406),
    "orleans": (47.9029, 1.9090),
    "mulhouse": (47.7508, 7.3359),
    "rouen": (49.4432, 1.0993),
    "caen": (49.1829, -0.3707),
    "nancy": (48.6921, 6.1844),
    "saint-paul": (-20.9844, 55.2702),
    "argenteuil": (48.9474, 2.2475),
    "montreuil": (48.8636, 2.4486),
    "roubaix": (50.6927, 3.1745),
    "tourcoing": (50.7239, 3.1612),
    "nanterre": (48.8923, 2.2071),
    "vitry-sur-seine": (48.7872, 2.3897),
    "creteil": (48.7906, 2.4555),
    "avignon": (43.9493, 4.8055),
    "poitiers": (46.5802, 0.3404),
    "fort-de-france": (14.6037, -61.0732),
    "courbevoie": (48.8965, 2.2553),
    "versailles": (48.8049, 2.1204),
    "colombes": (48.9226, 2.2522),
    "asnieres-sur-seine": (48.9131, 2.2873),
    "rueil-malmaison": (48.8780, 2.1813),
    "aubervilliers": (48.9145, 2.3845),
    "champigny-sur-marne": (48.8156, 2.5159),
    "saint-maur-des-fosses": (48.7980, 2.4937),
    "calais": (50.9513, 1.8587),
    "cannes": (43.5528, 7.0174),
    "antibes": (43.5808, 7.1239),
    "drancy": (48.9302, 2.4456),
    "merignac": (44.8326, -0.6976),
    "ajaccio": (41.9192, 8.7386),
    "saint-nazaire": (47.2735, -2.2128),
    "issy-les-moulineaux": (48.8260, 2.2737),
    "noisy-le-grand": (48.8487, 2.5530),
    "evry": (48.6293, 2.4408),
    "cergy": (49.0367, 2.0763),
    "pessac": (44.8067, -0.6311),
    "villeneuve-d'ascq": (50.6190, 3.1418),
    "valence": (44.9333, 4.8920),
    "quimper": (47.9963, -4.0985),
    "antony": (48.7536, 2.2978),
    "troyes": (48.2973, 4.0744),
    "ivry-sur-seine": (48.8156, 2.3839),
    "neuilly-sur-seine": (48.8847, 2.2691),
    "sarcelles": (48.9939, 2.3819),
    "venissieux": (45.6976, 4.8830),
    "clichy": (48.9044, 2.3068),
    "pau": (43.2951, -0.3708),
    "lorient": (47.7484, -3.3702),
    "la rochelle": (46.1591, -1.1520),
    "chambery": (45.5646, 5.9178),
    "beauvais": (49.4304, 2.0810),
    "cholet": (47.0608, -0.8780),
    "bourges": (47.0810, 2.3988),
    "saint-quentin": (49.8489, 3.2876),
    "niort": (46.3232, -0.4585),
    "vannes": (47.6582, -2.7608),
    "chalon-sur-saone": (46.7811, 4.8540),
    "annecy": (45.8992, 6.1294),
    "laval": (48.0737, -0.7704),
    "saint-louis": (47.5860, 7.5604),
    "albi": (43.9298, 2.1480),
    "bayonne": (43.4929, -1.4748),
    "brive-la-gaillarde": (45.1582, 1.5331),
    "evreux": (49.0260, 1.1500),
    "lens": (50.4310, 2.8324),
    "saint-malo": (48.6493, -2.0260),
    "frejus": (43.4332, 6.7370),
    "blois": (47.5863, 1.3359),
    "agen": (44.2032, 0.6212),
    "tarbes": (43.2333, 0.0782),
    "arles": (43.6766, 4.6280),
    "alençon": (48.4304, 0.0931),
    "carcassonne": (43.2130, 2.3491),
    "annemasse": (46.1942, 6.2363),
    "biarritz": (43.4832, -1.5586),
    "chateauroux": (46.8113, 1.6916),
    "saint-brieuc": (48.5135, -2.7659),
    "menton": (43.7755, 7.5024),
    "vincennes": (48.8472, 2.4399),
    "saint-cloud": (48.8400, 2.2189),
    "savigny-sur-orge": (48.6792, 2.3477),
    "epinay-sur-seine": (48.9555, 2.3122),
    "athis-mons": (48.7065, 2.3964),
    "longjumeau": (48.6961, 2.2999),
    "boulogne-sur-mer": (50.7264, 1.6147),
    "valenciennes": (50.3585, 3.5234),
    "saint-omer": (50.7531, 2.2541),
    "thonon-les-bains": (46.3697, 6.4806),
    "vichy": (46.1273, 3.4262),
    "vienne": (45.5253, 4.8743),
    "epernay": (49.0436, 3.9586),
    "monaco": (43.7384, 7.4246),
    "europe": (50.0, 10.0),  # rough EU centre as last-resort fallback
}


def geocode_french_city(city: Optional[str]) -> Optional[Tuple[float, float]]:
    if not city:
        return None
    key = unicodedata.normalize("NFKD", city.lower()).encode("ascii", "ignore").decode().strip()
    # try the exact normalized name
    if key in FR_CITIES:
        return FR_CITIES[key]
    # try first token (handles "Paris 11e" → "paris")
    head = key.split()[0] if key else ""
    if head in FR_CITIES:
        return FR_CITIES[head]
    # try with hyphenated head ("saint-denis", "saint-etienne")
    if "-" in key:
        joined = key.split(",")[0].strip()
        if joined in FR_CITIES:
            return FR_CITIES[joined]
    return None


def offer_coords(offer: dict) -> Optional[Tuple[float, float]]:
    """Resolve (lat, lon) for an offer from its own fields or by geocoding its city."""
    lat = offer.get("latitude") or offer.get("lat")
    lon = offer.get("longitude") or offer.get("lon") or offer.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return geocode_french_city(offer.get("city"))


# ---------- European countries ----------
EU_COUNTRIES = {
    "France", "Belgique", "Belgium", "Suisse", "Switzerland", "Luxembourg",
    "Allemagne", "Germany", "Espagne", "Spain", "Italie", "Italy",
    "Royaume-Uni", "United Kingdom", "UK", "Pays-Bas", "Netherlands",
    "Portugal", "Irlande", "Ireland", "Autriche", "Austria",
    "Pologne", "Poland", "Suède", "Sweden", "Norvège", "Norway",
    "Danemark", "Denmark", "Finlande", "Finland", "Tchéquie", "Czech Republic",
    "Hongrie", "Hungary", "Roumanie", "Romania", "Grèce", "Greece",
    "Bulgarie", "Bulgaria", "Slovaquie", "Slovakia", "Slovénie", "Slovenia",
    "Estonie", "Estonia", "Lettonie", "Latvia", "Lituanie", "Lithuania",
    "Croatie", "Croatia", "Malte", "Malta", "Chypre", "Cyprus",
    "Monaco", "Andorre", "Andorra", "Liechtenstein",
}

FR_NAMES = {"France", "FR", "fr"}


def is_french(country: Optional[str]) -> bool:
    if not country:
        return True  # unknown → treated as France by default per requirements
    return country.strip() in FR_NAMES or normalize_text(country) == "france"


def is_european(country: Optional[str]) -> bool:
    if not country:
        return False
    norm = normalize_text(country)
    for c in EU_COUNTRIES:
        if normalize_text(c) == norm:
            return True
    # ISO codes
    return country.strip().upper() in {
        "FR", "BE", "CH", "LU", "DE", "ES", "IT", "GB", "UK", "NL", "PT",
        "IE", "AT", "PL", "SE", "NO", "DK", "FI", "CZ", "HU", "RO", "GR",
        "BG", "SK", "SI", "EE", "LV", "LT", "HR", "MT", "CY", "MC", "AD", "LI",
    }


# Aliases FR ↔ EN ↔ ISO so a single user query matches all of them
COUNTRY_ALIASES: dict[str, set[str]] = {
    "france":      {"france", "fr"},
    "belgique":    {"belgique", "belgium", "be"},
    "suisse":      {"suisse", "switzerland", "ch"},
    "luxembourg":  {"luxembourg", "lu"},
    "allemagne":   {"allemagne", "germany", "de", "deutschland"},
    "espagne":     {"espagne", "spain", "es", "espana"},
    "italie":      {"italie", "italy", "it", "italia"},
    "royaume-uni": {"royaume uni", "united kingdom", "uk", "gb", "great britain", "england"},
    "pays-bas":    {"pays bas", "netherlands", "nl", "holland"},
    "portugal":    {"portugal", "pt"},
    "irlande":     {"irlande", "ireland", "ie"},
    "autriche":    {"autriche", "austria", "at"},
    "pologne":     {"pologne", "poland", "pl"},
    "danemark":    {"danemark", "denmark", "dk"},
    "suede":       {"suede", "sweden", "se"},
    "norvege":     {"norvege", "norway", "no"},
    "finlande":    {"finlande", "finland", "fi"},
    "grece":       {"grece", "greece", "gr"},
    "tchequie":    {"tchequie", "czech republic", "czechia", "cz"},
    "hongrie":     {"hongrie", "hungary", "hu"},
    "roumanie":    {"roumanie", "romania", "ro"},
}


def countries_match(filter_val: str, offer_country: Optional[str]) -> bool:
    """True if user filter (e.g. 'Allemagne') matches offer.country ('Germany' / 'DE' / etc.)."""
    if not offer_country:
        # Unknown country: only matches if filter is france/fr (default treatment)
        return normalize_text(filter_val) in ("france", "fr")
    f_norm = normalize_text(filter_val)
    o_norm = normalize_text(offer_country)
    if f_norm == o_norm:
        return True
    for canon, aliases in COUNTRY_ALIASES.items():
        if f_norm in aliases and o_norm in aliases:
            return True
    return False
