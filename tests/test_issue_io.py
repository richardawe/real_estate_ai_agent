import pytest

from workflows_lib.issue_io import (
    append_to_list,
    build_initial_body,
    get_field,
    new_workflow_front_matter,
    parse_front_matter,
    remove_from_list,
    render_front_matter,
    update_field,
)


SAMPLE_BODY = """\
---
workflow_id: rwa-2026-000001
type: buy
schema_version: 1
jurisdiction: england
shortlist: []
selected_property_id: null
---

Agent posted the first shortlist.
"""


# ---------------------------------------------------------------------------
# parse_front_matter
# ---------------------------------------------------------------------------


def test_parse_extracts_fields():
    fm, rest = parse_front_matter(SAMPLE_BODY)
    assert fm["workflow_id"] == "rwa-2026-000001"
    assert fm["type"] == "buy"
    assert fm["schema_version"] == 1
    assert fm["shortlist"] == []


def test_parse_returns_rest():
    _, rest = parse_front_matter(SAMPLE_BODY)
    assert "Agent posted" in rest


def test_parse_no_front_matter():
    body = "No front matter here."
    fm, rest = parse_front_matter(body)
    assert fm == {}
    assert rest == body


def test_parse_empty_body():
    fm, rest = parse_front_matter("")
    assert fm == {}
    assert rest == ""


# ---------------------------------------------------------------------------
# render_front_matter
# ---------------------------------------------------------------------------


def test_render_round_trip():
    fm, rest = parse_front_matter(SAMPLE_BODY)
    rendered = render_front_matter(fm, rest)
    fm2, rest2 = parse_front_matter(rendered)
    assert fm2 == fm
    assert rest2 == rest


# ---------------------------------------------------------------------------
# update_field
# ---------------------------------------------------------------------------


def test_update_existing_field():
    body = update_field(SAMPLE_BODY, "type", "rent")
    assert get_field(body, "type") == "rent"


def test_update_adds_new_field():
    body = update_field(SAMPLE_BODY, "selected_property_id", "prop-007")
    assert get_field(body, "selected_property_id") == "prop-007"


def test_update_preserves_rest():
    body = update_field(SAMPLE_BODY, "type", "rent")
    _, rest = parse_front_matter(body)
    assert "Agent posted" in rest


# ---------------------------------------------------------------------------
# get_field
# ---------------------------------------------------------------------------


def test_get_existing_field():
    assert get_field(SAMPLE_BODY, "workflow_id") == "rwa-2026-000001"


def test_get_missing_field_returns_default():
    assert get_field(SAMPLE_BODY, "nonexistent", "fallback") == "fallback"


def test_get_missing_field_default_none():
    assert get_field(SAMPLE_BODY, "nonexistent") is None


# ---------------------------------------------------------------------------
# append_to_list / remove_from_list
# ---------------------------------------------------------------------------


def test_append_to_list():
    body = append_to_list(SAMPLE_BODY, "shortlist", "prop-001")
    assert get_field(body, "shortlist") == ["prop-001"]


def test_append_to_list_idempotent():
    body = append_to_list(SAMPLE_BODY, "shortlist", "prop-001")
    body = append_to_list(body, "shortlist", "prop-001")
    assert get_field(body, "shortlist").count("prop-001") == 1


def test_append_multiple_items():
    body = append_to_list(SAMPLE_BODY, "shortlist", "prop-001")
    body = append_to_list(body, "shortlist", "prop-002")
    assert get_field(body, "shortlist") == ["prop-001", "prop-002"]


def test_remove_from_list():
    body = append_to_list(SAMPLE_BODY, "shortlist", "prop-001")
    body = append_to_list(body, "shortlist", "prop-002")
    body = remove_from_list(body, "shortlist", "prop-001")
    assert get_field(body, "shortlist") == ["prop-002"]


def test_remove_from_list_absent_is_noop():
    body = remove_from_list(SAMPLE_BODY, "shortlist", "prop-999")
    assert get_field(body, "shortlist") == []


# ---------------------------------------------------------------------------
# build_initial_body / new_workflow_front_matter
# ---------------------------------------------------------------------------


def test_build_initial_body_parses():
    fm = {"workflow_id": "rwa-2026-000002", "type": "rent"}
    body = build_initial_body(fm)
    parsed, _ = parse_front_matter(body)
    assert parsed["workflow_id"] == "rwa-2026-000002"


def test_build_initial_body_with_prose():
    fm = {"workflow_id": "rwa-2026-000003", "type": "buy"}
    body = build_initial_body(fm, prose="Workflow started.")
    _, rest = parse_front_matter(body)
    assert "Workflow started." in rest


def test_new_workflow_front_matter_structure():
    fm = new_workflow_front_matter(
        workflow_id="rwa-2026-000004",
        workflow_type="buy",
        jurisdiction="england",
        requirements={"budget_max": 400000},
        encrypted_pii="ENCRYPTED",
    )
    assert fm["workflow_id"] == "rwa-2026-000004"
    assert fm["type"] == "buy"
    assert fm["shortlist"] == []
    assert fm["documents"] == []
    assert fm["token_usage"] == 0
    assert "created_at" in fm
