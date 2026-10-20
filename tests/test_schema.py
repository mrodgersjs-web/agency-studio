import json

from agency_studio.cli import main
from agency_studio.contract import KINDS, LIST_FIELDS, REQUIRED_FIELDS
from agency_studio.schema import FIELD_DOCS, SCHEMA_VERSION, schema_as_dict


def test_schema_covers_every_field():
    data = schema_as_dict()
    assert set(data["front_matter"]["fields"]) == set(REQUIRED_FIELDS) | set(LIST_FIELDS)
    assert set(FIELD_DOCS) == set(REQUIRED_FIELDS) | set(LIST_FIELDS)


def test_schema_lists_all_kinds():
    data = schema_as_dict()
    assert all(kind in data["kind_rules"][0] for kind in KINDS)


def test_schema_engine_rules_named():
    rules = " ".join(schema_as_dict()["engine_rules"])
    for name in ("SELF_VERIFICATION", "BOUNDARY", "EVIDENCE", "VERDICT"):
        assert name in rules


def test_cli_schema_prints_json(capsys):
    assert main(["schema"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == SCHEMA_VERSION
