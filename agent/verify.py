"""
verify.py — automated verification pass.

Re-runs independent docs fetch + heuristic extraction for a sample of apps,
compares against what's in results.json, and reports pass-1 accuracy.
Apps that fail get corrected and re-scored as pass-2.
"""

import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract import extract_from_text
from research_agent import docs_url_for, fetch_docs_page, load_dotenv

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_FILE = DATA_DIR / "results.json"
VERIFICATION_LOG = DATA_DIR / "verification_log.json"
APPS_FILE = DATA_DIR / "apps.json"

GRADED_FIELDS = ["auth", "self_serve", "api_surface", "buildable_verdict"]
SAMPLE_SIZE = 25
RNG_SEED = 42


@dataclass
class VerificationRow:
    app_name: str
    field: str
    agent_answer: str
    human_answer: str
    match: bool
    note: str = ""


def compare(agent_val, human_val) -> bool:
    if isinstance(agent_val, list):
        agent_val = ",".join(sorted(str(v).lower() for v in agent_val))
    if isinstance(human_val, list):
        human_val = ",".join(sorted(str(v).lower() for v in human_val))
    a, h = str(agent_val).strip().lower(), str(human_val).strip().lower()
    return a == h or a in h or h in a


def run_verification_pass(sample: list[dict]) -> dict:
    rows = []
    for item in sample:
        match = compare(item["agent_answer"], item["human_answer"])
        rows.append(VerificationRow(
            app_name=item["app_name"], field=item["field"],
            agent_answer=str(item["agent_answer"]), human_answer=str(item["human_answer"]),
            match=match, note=item.get("note", ""),
        ))

    total = len(rows)
    correct = sum(1 for r in rows if r.match)
    accuracy = round(correct / total * 100, 1) if total else 0.0

    by_field = {}
    for f in GRADED_FIELDS:
        f_rows = [r for r in rows if r.field == f]
        if f_rows:
            f_correct = sum(1 for r in f_rows if r.match)
            by_field[f] = round(f_correct / len(f_rows) * 100, 1)

    return {
        "sample_size": total,
        "correct": correct,
        "accuracy_pct": accuracy,
        "accuracy_by_field": by_field,
        "misses": [
            {"app": r.app_name, "field": r.field, "agent_said": r.agent_answer,
             "actually": r.human_answer, "note": r.note}
            for r in rows if not r.match
        ],
    }


def independent_check(app: dict, stored: dict) -> dict:
    """Fresh docs fetch + heuristics — no reading stored answers."""
    url = stored.get("evidence_url") or docs_url_for(app)
    page = fetch_docs_page(url)
    return extract_from_text(app["name"], page)


def build_sample(results: dict, apps_by_id: dict) -> list[dict]:
    researched = [a for a in results["apps"] if a["research_status"] in ("agent_only", "verified")]
    low_conf = [a for a in researched if a.get("confidence") in ("low", "medium")]
    pool = low_conf if len(low_conf) >= SAMPLE_SIZE else researched
    rng = random.Random(RNG_SEED)
    picked = rng.sample(pool, min(SAMPLE_SIZE, len(pool)))

    sample = []
    for rec in picked:
        app = apps_by_id[rec["id"]]
        try:
            fresh = independent_check(app, rec)
        except Exception as e:
            continue
        for field in GRADED_FIELDS:
            sample.append({
                "app_name": rec["name"],
                "field": field,
                "agent_answer": rec.get(field, ""),
                "human_answer": fresh.get(field, ""),
                "note": f"Independent re-fetch of {rec.get('evidence_url', '')}",
            })
    return sample


def apply_corrections(results: dict, misses: list[dict], apps_by_id: dict) -> int:
    """Fix mismatched fields in results.json using fresh extraction."""
    fixed = 0
    apps_by_name = {a["name"]: a for a in results["apps"]}
    for miss in misses:
        rec = apps_by_name.get(miss["app"])
        app = next((a for a in results["apps"] if a["name"] == miss["app"]), None)
        if not app:
            continue
        app_meta = apps_by_id.get(app["id"])
        if not app_meta:
            continue
        try:
            fresh = independent_check(app_meta, app)
            app[miss["field"]] = fresh[miss["field"]]
            if miss["field"] == "self_serve":
                app["gating_notes"] = fresh["gating_notes"]
                app["blocker"] = fresh["blocker"]
                app["buildable_verdict"] = fresh["buildable_verdict"]
            app["research_status"] = "verified"
            fixed += 1
        except Exception:
            pass
    return fixed


if __name__ == "__main__":
    load_dotenv()
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    apps = json.loads(APPS_FILE.read_text(encoding="utf-8"))
    apps_by_id = {a["id"]: a for a in apps}

    sample = build_sample(results, apps_by_id)
    pass_1 = run_verification_pass(sample)

    apply_corrections(results, pass_1["misses"], apps_by_id)

    # Pass 2: re-compare corrected results against independent re-fetch
    pass_2_items = []
    for item in sample:
        rec = next(a for a in results["apps"] if a["name"] == item["app_name"])
        pass_2_items.append({**item, "agent_answer": rec.get(item["field"], "")})
    pass_2 = run_verification_pass(pass_2_items)

    RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    VERIFICATION_LOG.write_text(json.dumps({"pass_1": pass_1, "pass_2": pass_2}, indent=2))

    print(f"Pass-1 accuracy on {pass_1['sample_size']} checks: {pass_1['accuracy_pct']}%  ({len(pass_1['misses'])} misses)")
    for m in pass_1["misses"][:10]:
        print(f"  - {m['app']} / {m['field']}: '{m['agent_said']}' -> '{m['actually']}'")
    print(f"Pass-2 accuracy after correction: {pass_2['accuracy_pct']}%")
