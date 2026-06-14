"""Tests for dedup.dedupe_offers — fuzzy cross-source deduplication."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dedup import dedupe_offers, _canonical_title_tokens, _fingerprint


def test_exact_url_dedup():
    offers = [
        {"offer_id": "a", "external_url": "https://x/1", "title": "Stage Dev", "company_name": "EDF", "city": "Paris"},
        {"offer_id": "b", "external_url": "https://x/1", "title": "Stage Dev", "company_name": "EDF", "city": "Paris"},
    ]
    out = dedupe_offers(offers)
    assert len(out) == 1
    assert out[0]["offer_id"] == "a"


def test_fuzzy_cross_source_merge():
    """Same job from Adzuna + Jooble with slightly different titles → merged."""
    offers = [
        {
            "offer_id": "adz_1", "external_url": "https://adzuna/1",
            "title": "Stage Développeur Python H/F",
            "company_name": "Crédit Agricole", "city": "Paris",
            "source": "Adzuna", "source_priority": 5, "description": "Long description...",
        },
        {
            "offer_id": "joo_1", "external_url": "https://jooble/abc",
            "title": "Développeur Python (Stage) - F/H",
            "company_name": "CREDIT AGRICOLE S.A.", "city": "Paris",
            "source": "Jooble", "source_priority": 5, "description": "Short",
        },
    ]
    out = dedupe_offers(offers)
    assert len(out) == 1
    keeper = out[0]
    # Keeper is the one with longer description (better score)
    assert keeper["source"] == "Adzuna"
    assert "Jooble" in keeper.get("duplicate_sources", [])
    assert keeper.get("duplicate_count") == 1


def test_different_companies_not_merged():
    offers = [
        {"offer_id": "1", "title": "Stage Data Scientist", "company_name": "Total", "city": "Paris", "source": "A", "source_priority": 5},
        {"offer_id": "2", "title": "Stage Data Scientist", "company_name": "EDF",   "city": "Paris", "source": "B", "source_priority": 5},
    ]
    out = dedupe_offers(offers)
    assert len(out) == 2


def test_different_cities_not_merged():
    offers = [
        {"offer_id": "1", "title": "Stage Marketing Digital", "company_name": "Orange", "city": "Paris",  "source": "A", "source_priority": 5},
        {"offer_id": "2", "title": "Stage Marketing Digital", "company_name": "Orange", "city": "Lyon",   "source": "B", "source_priority": 5},
    ]
    out = dedupe_offers(offers)
    assert len(out) == 2


def test_higher_priority_wins():
    offers = [
        {"offer_id": "low",  "title": "Alternance Chef de projet Marketing", "company_name": "Carrefour", "city": "Lille",
         "source": "Arbeitnow", "source_priority": 3, "description": "x"},
        {"offer_id": "high", "title": "Alternance Chef de projet Marketing", "company_name": "Carrefour", "city": "Lille",
         "source": "FranceTravail", "source_priority": 9, "description": "x"},
    ]
    out = dedupe_offers(offers)
    assert len(out) == 1
    assert out[0]["source"] == "FranceTravail"
    assert "Arbeitnow" in out[0].get("duplicate_sources", [])


def test_insufficient_signal_passes_through():
    """Offer with too-short title (single distinctive token) is not grouped."""
    offers = [
        {"offer_id": "1", "title": "Stage", "company_name": "Acme", "city": "Paris", "source": "A"},
        {"offer_id": "2", "title": "Stage", "company_name": "Acme", "city": "Paris", "source": "B"},
    ]
    out = dedupe_offers(offers)
    # No fingerprint → both kept (de-duped only by id)
    assert len(out) == 2


def test_canonical_tokens_strip_noise():
    t1 = _canonical_title_tokens("Stage Développeur Full-Stack H/F (6 mois)")
    t2 = _canonical_title_tokens("Développeur Fullstack Stage 6 mois F/H")
    # "full-stack" vs "fullstack" are different tokens — that's fine, but
    # "developpeur" must be common.
    assert "developpeur" in t1
    assert "developpeur" in t2


def test_no_mutation_of_input():
    offers = [
        {"offer_id": "1", "title": "Stage Dev Python", "company_name": "EDF", "city": "Paris", "source": "A", "source_priority": 5},
        {"offer_id": "2", "title": "Stage Dev Python", "company_name": "EDF", "city": "Paris", "source": "B", "source_priority": 5},
    ]
    snapshot = [dict(o) for o in offers]
    dedupe_offers(offers)
    assert offers == snapshot


def test_empty_input():
    assert dedupe_offers([]) == []
    assert dedupe_offers(None) == []  # type: ignore


def test_skips_non_dict_entries():
    offers = [
        {"offer_id": "1", "title": "Stage Dev", "company_name": "EDF", "city": "Paris"},
        "garbage",
        None,
    ]
    out = dedupe_offers(offers)
    assert len(out) == 1


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
