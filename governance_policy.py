"""Local, versioned context for policy reviews; no external certificate lookup."""
import hashlib
import json
from pathlib import Path

REFERENCE_PATH = Path(__file__).resolve().parent / "governance" / "references.json"


def reference_context():
    mapping = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    references = [item for item in mapping["references"] if item.get("checked_on") and item.get("provisions")]
    context = {"map_version": mapping["map_version"], "references": references,
               "scope": mapping["scope"], "certificate_validation": "not_performed"}
    context["sha256"] = hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return context


def policy_references(rule_id, context=None):
    context = context if context is not None else reference_context()
    return [item for item in context["references"] if rule_id in item.get("related_policy_ids", [])]
