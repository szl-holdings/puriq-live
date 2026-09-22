"""Regression lock for PURIQ estate authority and publication boundaries."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "SZL_ESTATE_BINDING.json"
SOURCE_PIN = ROOT / "SOURCE_PIN.md"
FOLD = ROOT / "FOLD.md"
SPACE = ROOT / "SPACE.md"


def test_local_estate_binding_names_the_current_canonical_projection() -> None:
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    assert binding["schema"] == "szl.estate.binding/v1"
    assert binding["organ"] == "puriq"
    assert binding["canonical_contract"].endswith("/.github/blob/main/estate/alignment.v1.json")
    assert binding["hub_surface"] == "SZLHOLDINGS/finance"
    assert binding["hub_publisher"] == (
        "szl-holdings/a11oy:.github/workflows/hf-publish-vertical-flagships.yml"
    )
    assert binding["duplicate_hub_space_forbidden"] is True


def test_source_authority_documents_match_the_binding() -> None:
    source_pin = SOURCE_PIN.read_text(encoding="utf-8")
    fold = FOLD.read_text(encoding="utf-8")

    for document in (source_pin, fold):
        assert "szl-holdings/puriq-live" in document
        assert "szl-holdings/szl-formulas" in document
        assert "szl-holdings/a11oy:verticals/finance" in document
        assert "SZLHOLDINGS/finance" in document

    stale_claims = (
        "SZLHOLDINGS/puriq-markets",
        "Space visibility | private (initial)",
        "Space status | ROADMAP until Hub runtime readback",
        "formula authority | NONE",
        "This repository is a generated thin adapter",
    )
    combined = source_pin + "\n" + fold
    for claim in stale_claims:
        assert claim not in combined


def test_space_card_is_source_material_not_a_publication_receipt() -> None:
    card = SPACE.read_text(encoding="utf-8")
    assert "sdk: docker" in card
    assert "app_port: 7860" in card
    assert "SZLHOLDINGS/finance" in card
    assert "source material only" in card
    assert "does not prove" in card
    assert "sdk: gradio" not in card
