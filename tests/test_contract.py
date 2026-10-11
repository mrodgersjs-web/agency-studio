import pytest

from agency_studio.contract import ContractError, load_contract, load_contracts, parse_front_matter, validate_data
from agency_studio.engine import glob_to_regex, normalize, path_allowed

GOOD = """---
name: builder
kind: builder
purpose: build
allow_write:
  - src/**
requires_evidence: [diff]
---
# body
"""


def test_parse_inline_and_block_lists():
    data, body = parse_front_matter(GOOD)
    assert data["allow_write"] == ["src/**"] and data["requires_evidence"] == ["diff"]
    assert body == "# body"


@pytest.mark.parametrize(
    "text",
    ["no front matter", "---\nname: x\n", "---\nname x\n---\n", "---\na: 1\na: 2\n---\n", "---\n- orphan\n---\n"],
)
def test_parse_rejects_malformed(text):
    with pytest.raises(ContractError):
        parse_front_matter(text)


def test_shipped_contracts_all_valid():
    contracts = load_contracts("roles")
    assert set(contracts) == {"scout", "planner", "builder", "reviewer", "verifier", "documenter"}


def test_validator_rules():
    base = {"name": "v", "kind": "verifier", "purpose": "p", "requires_evidence": ["test_output"]}
    assert validate_data(base) == []
    assert any("read-only" in e for e in validate_data({**base, "allow_write": ["src/**"]}))
    assert any("requires_evidence" in e for e in validate_data({**base, "requires_evidence": []}))
    assert any("kind" in e for e in validate_data({**base, "kind": "wizard"}))
    assert any("unknown field" in e for e in validate_data({**base, "powers": []}))
    assert any("missing required" in e for e in validate_data({"name": "x"}))
    assert any("'..'" in e for e in validate_data({**base, "kind": "scout", "allow_read": ["../x"]}))
    assert any("name" in e for e in validate_data({**base, "name": "Bad Name"}))


def test_load_contract_error_names_file(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nname: x\n---\n")
    with pytest.raises(ContractError, match="x.md"):
        load_contract(f)


def test_set_validation_overlap_and_duplicates(tmp_path):
    (tmp_path / "b.md").write_text(GOOD)
    (tmp_path / "b2.md").write_text(GOOD)
    with pytest.raises(ContractError, match="duplicate"):
        load_contracts(tmp_path)


def test_glob_semantics():
    assert glob_to_regex("src/**").match("src/a/b.py")
    assert glob_to_regex("src/*.py").match("src/a.py")
    assert not glob_to_regex("src/*.py").match("src/a/b.py")
    assert normalize("../etc") is None and normalize("/etc") is None
    assert normalize("src/./a/../b") == "src/b"
    assert not path_allowed(["src/**"], "src/../secrets/key")
