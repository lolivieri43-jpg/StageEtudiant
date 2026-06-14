"""Offer deduplication — fuzzy matching across job sources.

The various external job APIs (France Travail, Adzuna, Jooble, La Bonne Alternance,
Ashby, Greenhouse, Arbeitnow, Remotive, Jobicy, RemoteOK, EURES, etc.) frequently
republish the same job under different URLs and slightly different titles.

This module exposes a single function `dedupe_offers(offers)` which:

1. Performs a first pass keyed by `external_url` / `offer_id` (exact dedupe).
2. Computes a fuzzy fingerprint built from
       (normalized company, canonical title token-set, normalized city)
   and merges offers that share it.
3. Within each group, keeps the offer with the highest `source_priority`
   (or most descriptive content when priorities tie), and attaches a
   `duplicate_sources` list with the other sources for transparency.

The function is intentionally pure (no DB / IO) so it can be reused by every
orchestrator and unit-tested in isolation.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from geo_search import normalize_text


# Tokens we strip from titles before fingerprinting — gender markers, year tags,
# duration hints and other noise that makes the same job look different.
_TITLE_NOISE = {
    "h", "f", "hf", "fh", "mf", "fm",
    "stage", "stagiaire", "internship", "intern", "trainee",
    "alternance", "alternant", "apprentice", "apprentissage", "apprenti",
    "junior", "graduate", "etudiant", "student",
    "cdi", "cdd", "freelance",
    "mois", "month", "months", "an", "ans", "year", "years",
    "fr", "france", "remote", "teletravail", "hybride", "hybrid",
}

# Words used as additional location tokens we never want as title signal.
_RE_PARENS = re.compile(r"\([^)]*\)")
_RE_BRACKETS = re.compile(r"\[[^\]]*\]")
_RE_DURATION = re.compile(r"\b\d+\s?(?:mois|month|months|an|ans|year|years|sem|weeks?)\b")
_RE_DIGIT_TOKEN = re.compile(r"\b\d+\b")


def _canonical_title_tokens(title: Optional[str]) -> frozenset:
    """Return a frozenset of meaningful tokens from a job title.

    Two titles that share the same canonical token-set are considered
    "the same job" by the fuzzy fingerprint.
    """
    if not title:
        return frozenset()
    t = normalize_text(title)
    t = _RE_PARENS.sub(" ", t)
    t = _RE_BRACKETS.sub(" ", t)
    t = _RE_DURATION.sub(" ", t)
    t = _RE_DIGIT_TOKEN.sub(" ", t)
    # Replace punctuation/slashes
    t = re.sub(r"[/_\-+|•·,]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    tokens = [w for w in t.split() if len(w) >= 3 and w not in _TITLE_NOISE]
    return frozenset(tokens)


def _normalize_company(name: Optional[str]) -> str:
    """Stronger company normalization on top of `normalize_text`.

    `normalize_text` already strips diacritics and common suffixes, but tokens
    like "S.A." get split into "s a" by punctuation removal — we then drop any
    trailing single/two-letter tokens that survived (s, a, sa, fr, eu, ...).
    """
    n = normalize_text(name)
    if not n:
        return ""
    tokens = [t for t in n.split() if len(t) >= 3]
    return " ".join(tokens) or n


def _fingerprint(offer: Dict) -> Optional[tuple]:
    """Build a fuzzy fingerprint for an offer.

    Returns None when not enough signal is available to safely group offers
    (in that case the offer passes through untouched, keyed by its unique id).
    """
    company = _normalize_company(offer.get("company_name"))
    city = normalize_text(offer.get("city"))
    tokens = _canonical_title_tokens(offer.get("title"))
    # Need at least company + 2 distinctive tokens to call it the same job.
    if not company or len(tokens) < 2:
        return None
    return (company, tokens, city)


def _score(offer: Dict) -> tuple:
    """Higher = better representative. Used to pick a group's keeper."""
    priority = int(offer.get("source_priority") or 0)
    desc_len = len(offer.get("description") or "")
    has_url = 1 if offer.get("external_url") else 0
    has_logo = 1 if offer.get("company_logo") else 0
    has_coords = 1 if (offer.get("coords") or offer.get("lat")) else 0
    has_salary = 1 if offer.get("salary") else 0
    return (priority, has_url, has_logo, has_coords, has_salary, desc_len)


def dedupe_offers(offers: Iterable[Dict]) -> List[Dict]:
    """Deduplicate a list of offers across sources.

    - Exact dedupe on external_url / offer_id first.
    - Fuzzy dedupe on (company, title-tokens, city) second.
    - Annotates the kept offer with `duplicate_sources` (list of source names
      from the merged duplicates) and `duplicate_count`.
    """
    # Pass 1 — exact URL/id dedupe (preserves first occurrence).
    seen_ids: set = set()
    uniq: List[Dict] = []
    for o in offers or []:
        if not isinstance(o, dict):
            continue
        key = o.get("external_url") or o.get("offer_id")
        if key:
            if key in seen_ids:
                continue
            seen_ids.add(key)
        uniq.append(o)

    # Pass 2 — fuzzy grouping.
    groups: Dict[tuple, List[Dict]] = {}
    passthrough: List[Dict] = []
    for o in uniq:
        fp = _fingerprint(o)
        if fp is None:
            passthrough.append(o)
            continue
        groups.setdefault(fp, []).append(o)

    deduped: List[Dict] = list(passthrough)
    for items in groups.values():
        if len(items) == 1:
            deduped.append(items[0])
            continue
        items.sort(key=_score, reverse=True)
        keeper = dict(items[0])  # shallow copy so we don't mutate input
        other_sources = []
        for other in items[1:]:
            src = other.get("source")
            if src and src != keeper.get("source") and src not in other_sources:
                other_sources.append(src)
        if other_sources:
            keeper["duplicate_sources"] = other_sources
            keeper["duplicate_count"] = len(items) - 1
        deduped.append(keeper)

    return deduped
