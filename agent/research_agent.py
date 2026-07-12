"""
research_agent.py — Composio-only research pipeline.

For every app in data/apps.json:
  1. Query Composio toolkit catalog (composio.toolkits API)
  2. Fetch the docs URL (HTTP) for gating/surface signals
  3. Merge Composio metadata + docs heuristics into AppRecord
  4. Write data/results.json

No Anthropic or other LLM API keys required — only COMPOSIO_API_KEY.
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent))
from extract import extract_from_text

DATA_DIR = Path(__file__).parent.parent / "data"
APPS_FILE = DATA_DIR / "apps.json"
RESULTS_FILE = DATA_DIR / "results.json"
RUN_LOG_FILE = DATA_DIR / "run_log.jsonl"

AUTH_MAP = {
    "OAUTH2": "OAuth2",
    "OAUTH1": "OAuth1",
    "OAUTH1A": "OAuth1",
    "API_KEY": "API key",
    "BEARER_TOKEN": "API key",
    "BASIC": "Basic",
    "BASIC_WITH_JWT": "Basic",
    "SERVICE_ACCOUNT": "Service account",
    "NO_AUTH": "None",
    "GOOGLE_SERVICE_ACCOUNT": "Service account",
}

COMPOSIO_TOOLKIT_CACHE: dict[str, dict] | None = None
COMPOSIO_VERSIONS: dict[str, str] = {}
USER_ID = "toolkit_audit"


@dataclass
class AppRecord:
    id: int
    category: str
    name: str
    auth: list = field(default_factory=list)
    self_serve: str = "unknown"
    gating_notes: str = ""
    api_surface: str = ""
    mcp_status: str = ""
    buildable_verdict: str = "unknown"
    blocker: Optional[str] = None
    evidence_url: str = ""
    research_status: str = "queued"
    confidence: str = "low"
    source_notes: str = ""


def load_dotenv():
    env_file = DATA_DIR.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def docs_url_for(app: dict) -> str:
    hint = app["hint"]
    if hint.startswith("http"):
        return hint
    return f"https://{hint}"


def log_run(app_name: str, event: str):
    with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"app": app_name, "event": event, "ts": time.time()}) + "\n")


def get_composio_client():
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise RuntimeError("COMPOSIO_API_KEY is required — set it in .env")
    from composio import Composio
    return Composio(api_key=api_key)


def composio_search_toolkits(app_name: str) -> Optional[str]:
    """Use COMPOSIO_SEARCH_TOOLS (no extra auth) to find a matching toolkit slug."""
    client = get_composio_client()
    try:
        result = client.tools.execute(
            "COMPOSIO_SEARCH_TOOLS",
            user_id=USER_ID,
            arguments={"use_case": f"{app_name} API integration authentication"},
            dangerously_skip_version_check=True,
        )
        data = result.get("data") if isinstance(result, dict) else getattr(result, "data", None)
        if not data:
            return None
        results = data.get("results") if isinstance(data, dict) else []
        if not results:
            return None
        slugs = results[0].get("primary_tool_slugs") or []
        return slugs[0].lower() if slugs else None
    except Exception:
        return None


def load_composio_toolkits() -> dict[str, dict]:
    global COMPOSIO_TOOLKIT_CACHE
    if COMPOSIO_TOOLKIT_CACHE is not None:
        return COMPOSIO_TOOLKIT_CACHE

    client = get_composio_client()
    index: dict[str, dict] = {}
    cursor = None
    while True:
        kwargs = {"limit": 100, "sort_by": "alphabetically"}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.toolkits.list(**kwargs)
        for item in resp.items:
            data = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            index[item.slug] = data
            index[norm(item.name)] = data
            meta = data.get("meta") or {}
            if meta.get("version"):
                COMPOSIO_VERSIONS[item.slug] = meta["version"]
        cursor = getattr(resp, "next_cursor", None) or getattr(resp, "cursor", None)
        if not cursor:
            break

    COMPOSIO_TOOLKIT_CACHE = index
    return index


def match_composio_slug(app: dict, index: dict[str, dict], *, use_search: bool = False) -> Optional[str]:
    candidates = [norm(app["name"].split("(")[0]), norm(app["name"])]
    hint = app["hint"]
    host = re.sub(r"^https?://", "", hint).split("/")[0] if hint.startswith("http") else hint.split("/")[0]
    candidates.append(norm(host.split(".")[0]))

    alias = {
        "zohocrm": "zoho", "zohocliq": "zoho", "metaads": "meta", "threadsmeta": "meta",
        "linkedinads": "linkedin", "googleads": "googleads", "whatsappbusiness": "whatsapp",
        "magentoadobecommerce": "adobe", "salesforcecommercecloud": "salesforce",
        "amazonsellingpartner": "amazon", "youtubetranscript": "youtube", "otterai": "otter",
        "notebooklm": "google", "mermaidcli": "mermaid", "paygentconnect": "paygent",
        "helpscout": "helpscout", "woocommerce": "woocommerce", "bigcommerce": "bigcommerce",
        "twilio": "twilio", "plaid": "plaid", "mongodb": "mongodb", "smartsheet": "smartsheet",
    }
    for c in list(candidates):
        if c in alias:
            candidates.append(alias[c])

    slugs = set(index.keys())
    for c in candidates:
        if c in slugs and c in index and index[c].get("slug") == c:
            return c
        for slug in slugs:
            if len(c) >= 4 and slug == c:
                return slug
            if len(c) >= 5 and len(slug) >= 5 and (c in slug or slug in c):
                hit = index.get(slug)
                if hit and hit.get("slug") == slug:
                    return slug

    if use_search:
        return composio_search_toolkits(app["name"])
    return None


def auth_from_toolkit(data: dict) -> list[str]:
    methods = []
    deprecated = data.get("deprecated") or {}
    for item in deprecated.get("raw_proxy_info_by_auth_schemes") or []:
        method = item.get("auth_method")
        if method:
            methods.append(AUTH_MAP.get(method, method.replace("_", " ").title()))
    for cfg in data.get("auth_config_details") or []:
        mode = cfg.get("mode") or cfg.get("auth_mode")
        if mode:
            methods.append(AUTH_MAP.get(mode, str(mode).replace("_", " ").title()))
    if data.get("no_auth"):
        methods.append("None")
    deduped = []
    for m in methods:
        if m not in deduped:
            deduped.append(m)
    return deduped or ["OAuth2"]


def toolkit_base_record(data: dict) -> dict:
    meta = data.get("meta") or {}
    tools_count = meta.get("tools_count")
    description = meta.get("description") or data.get("name", "")
    api_surface = (
        f"Composio toolkit — {int(tools_count)} tools. {description}"
        if tools_count else f"Composio toolkit. {description}"
    )
    return {
        "auth": auth_from_toolkit(data),
        "api_surface": api_surface,
        "mcp_status": "Available as Composio MCP server",
        "buildable_verdict": "ready",
        "blocker": None,
        "evidence_url": meta.get("app_url") or "",
        "source_notes": f"composio_toolkit:{data.get('slug')}",
    }


def fetch_docs_page(url: str) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ComposioToolkitAudit/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    last_err = None
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            if resp.status_code >= 500 and attempt == 0:
                time.sleep(1)
                continue
            resp.raise_for_status()
            html = resp.text
            try:
                import trafilatura
                text = trafilatura.extract(html, include_comments=False, include_tables=True)
                if text and len(text.strip()) > 200:
                    return text[:14000]
            except Exception:
                pass
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
            return text[:14000] if text else None
        except Exception as e:
            last_err = e
    raise RuntimeError(f"fetch failed for {url}: {last_err}")


def merge_composio_and_docs(composio_rec: dict, docs_rec: dict) -> dict:
    """Composio gives auth/surface; docs heuristics override gating (more accurate)."""
    merged = {**composio_rec}
    merged["self_serve"] = docs_rec["self_serve"]
    merged["gating_notes"] = docs_rec["gating_notes"]
    merged["buildable_verdict"] = docs_rec["buildable_verdict"]
    merged["blocker"] = docs_rec["blocker"]
    if docs_rec["mcp_status"] != "None official":
        merged["mcp_status"] = docs_rec["mcp_status"]
    if docs_rec["confidence"] == "low":
        merged["confidence"] = "medium"
    else:
        merged["confidence"] = docs_rec["confidence"]
    if docs_rec["buildable_verdict"] in ("partial", "blocked"):
        merged["confidence"] = "medium"
    return merged


def research_app(app: dict) -> AppRecord:
    record = AppRecord(id=app["id"], category=app["category"], name=app["name"])
    docs_url = docs_url_for(app)
    record.evidence_url = docs_url

    page_text = None
    docs_rec = None
    try:
        page_text = fetch_docs_page(docs_url)
        docs_rec = extract_from_text(app["name"], page_text)
        log_run(app["name"], "docs_fetch_ok")
    except Exception as e:
        log_run(app["name"], f"docs_fetch_error:{e}")

    index = load_composio_toolkits()
    slug = match_composio_slug(app, index, use_search=False)
    if not slug:
        slug = match_composio_slug(app, index, use_search=True)
    composio_data = None
    if slug:
        data = index.get(slug)
        if not data or data.get("slug") != slug:
            try:
                tk = get_composio_client().toolkits.get(slug)
                data = tk.model_dump() if hasattr(tk, "model_dump") else tk.dict()
            except Exception:
                data = None
        if data:
            composio_data = toolkit_base_record(data)
            log_run(app["name"], f"composio_toolkit:{slug}")

    if composio_data and docs_rec:
        merged = merge_composio_and_docs(composio_data, docs_rec)
        record.__dict__.update(merged)
        if not record.evidence_url:
            record.evidence_url = docs_url
        record.research_status = "agent_only"
        record.source_notes = composio_data["source_notes"] + "+docs_heuristics"
    elif composio_data:
        record.__dict__.update(composio_data)
        record.self_serve = "self-serve"
        record.gating_notes = "Composio toolkit available; gating not confirmed from docs (fetch failed)."
        record.confidence = "medium"
        record.research_status = "agent_only"
    elif docs_rec:
        record.__dict__.update(docs_rec)
        record.evidence_url = docs_url
        record.research_status = "agent_only"
        record.source_notes = "docs_heuristics"
        log_run(app["name"], "docs_heuristics_only")
    else:
        record.research_status = "queued"
        record.source_notes = "docs fetch failed and no composio toolkit match"
        log_run(app["name"], "queued")

    return record


def run_pipeline(*, force: bool = False, limit: int | None = None):
    load_dotenv()
    print("Loading Composio toolkit catalog...", flush=True)
    load_composio_toolkits()
    print(f"Indexed {len(COMPOSIO_TOOLKIT_CACHE or {})} toolkit entries.", flush=True)

    all_apps = json.loads(APPS_FILE.read_text(encoding="utf-8"))
    to_process = all_apps[:limit] if limit else all_apps

    records = []
    for i, app in enumerate(to_process):
        print(f"[{i+1}/{len(to_process)}] {app['name']}...", flush=True)
        records.append(asdict(research_app(app)))
        time.sleep(0.15)

    verified = sum(1 for r in records if r["research_status"] == "verified")
    agent_only = sum(1 for r in records if r["research_status"] == "agent_only")
    queued = sum(1 for r in records if r["research_status"] == "queued")

    output = {
        "meta": {
            "total_apps": len(records),
            "researched": verified + agent_only,
            "verified": verified,
            "agent_only": agent_only,
            "queued": queued,
            "generated_at": time.strftime("%Y-%m-%d"),
            "pipeline": "composio_api + docs_heuristics (no anthropic)",
        },
        "apps": sorted(records, key=lambda x: x["id"]),
    }
    RESULTS_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Done. researched={verified + agent_only} agent_only={agent_only} queued={queued}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_pipeline(limit=args.limit)
