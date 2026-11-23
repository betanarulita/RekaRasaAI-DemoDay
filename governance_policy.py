"""Local, versioned context for policy reviews; no external certificate lookup."""
import hashlib
import json
from pathlib import Path

REFERENCE_PATH = Path(__file__).resolve().parent / "governance" / "references.json"

REFERENCE_CATEGORIES = {
    "cosmetics_only": {"cosmetics"},
    "consumer_goods_and_services": {"cosmetics", "food_beverage", "general_consumer_product", "unknown"},
    "general": {"cosmetics", "food_beverage", "general_consumer_product", "unknown"},
    "all_products": {"cosmetics", "food_beverage", "general_consumer_product", "unknown"},
}


def _context_hash(context):
    context.pop("sha256", None)
    context["sha256"] = hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return context


def filter_reference_context(context, product_category=None):
    references = context.get("references", [])
    if product_category:
        references = [item for item in references
                      if product_category in REFERENCE_CATEGORIES.get(item.get("category"), set())]
    filtered = {key: value for key, value in context.items() if key != "sha256"}
    filtered["references"] = references
    filtered["product_category"] = product_category or "unconfirmed"
    return _context_hash(filtered)


def reference_context(product_category=None):
    mapping = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    references = [item for item in mapping["references"] if item.get("checked_on") and item.get("provisions")]
    context = {"map_version": mapping["map_version"], "references": references,
               "scope": mapping["scope"], "certificate_validation": "not_performed"}
    context = _context_hash(context)
    return filter_reference_context(context, product_category) if product_category else context


def policy_references(rule_id, context=None):
    context = context if context is not None else reference_context()
    return [item for item in context["references"] if rule_id in item.get("related_policy_ids", [])]
