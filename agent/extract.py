"""Rule-based field extraction from docs page text (no external LLM)."""

import re
from typing import Optional


def _text_lower(text: str) -> str:
    return text.lower()


def detect_auth(text: str) -> list[str]:
    t = _text_lower(text)
    found = []
    patterns = [
        (r"\boauth\s*2\.0\b|\boauth2\b", "OAuth2"),
        (r"\boauth\s*1\.0\b|\boauth1\b", "OAuth1"),
        (r"\bapi key\b|\bapi keys\b|\bapikey\b", "API key"),
        (r"\bbearer token\b|\bbearer auth\b", "API key"),
        (r"\baccess token\b", "Access token"),
        (r"\bbot token\b", "Bot token"),
        (r"\bpersonal access token\b|\bpat\b", "PAT"),
        (r"\bbasic auth\b|\bhttp basic\b", "Basic"),
        (r"\bservice account\b", "Service account"),
        (r"\bno auth\b|\bno authentication\b", "None"),
    ]
    for pat, label in patterns:
        if re.search(pat, t) and label not in found:
            found.append(label)
    if not found:
        if re.search(r"\boauth\b", t):
            found.append("OAuth2")
        elif re.search(r"\btoken\b", t):
            found.append("API key")
    return found or ["Other"]


def detect_gating(text: str) -> tuple[str, str, Optional[str]]:
    t = _text_lower(text)
    gated_signals = [
        r"contact sales", r"talk to sales", r"request access", r"sales team",
        r"enterprise plan", r"account manager", r"signed contract", r"custom pricing",
        r"not publicly available", r"by invitation", r"apply for access",
    ]
    mixed_signals = [
        r"app review", r"manual approval", r"developer token", r"business verification",
        r"production access", r"sandbox only", r"test account only", r"approval process",
        r"submit for review", r"partner program", r"wait for approval",
    ]
    self_signals = [
        r"sign up", r"create an account", r"free trial", r"instant", r"self-serve",
        r"generate.*api key", r"create.*app", r"developer portal", r"no approval",
    ]

    gated = sum(1 for p in gated_signals if re.search(p, t))
    mixed = sum(1 for p in mixed_signals if re.search(p, t))
    self = sum(1 for p in self_signals if re.search(p, t))

    if gated >= 2 or (gated >= 1 and self == 0):
        verdict = "gated"
        notes = "Access appears to require sales contact or a paid/contractual gate."
        blocker = "Sales or contract required before API credentials are issued"
    elif mixed >= 1 or (self >= 1 and gated >= 1):
        verdict = "mixed"
        notes = "Signup is self-serve but production use likely needs manual approval."
        blocker = "Manual approval step between signup and production access"
    elif self >= 1:
        verdict = "self-serve"
        notes = "Developer signup and credential issuance appear self-serve from docs."
        blocker = None
    else:
        verdict = "mixed"
        notes = "Gating unclear from docs alone; assume a review step may exist."
        blocker = None

    return verdict, notes, blocker


def detect_api_surface(text: str, app_name: str) -> str:
    t = _text_lower(text)
    if re.search(r"\bcli only\b|\bcommand.?line tool\b|\bno (?:public )?api\b|\bno http api\b", t):
        return "None (CLI only, no HTTP API)"
    parts = []
    if re.search(r"\bgraphql\b", t):
        parts.append("GraphQL")
    if re.search(r"\bgrpc\b", t):
        parts.append("gRPC")
    if re.search(r"\brest\b|\brestful\b|\bhttp api\b|\bweb api\b", t):
        parts.append("REST")
    if re.search(r"\bwebsocket\b|\bsocket mode\b", t):
        parts.append("WebSocket")
    if not parts:
        if re.search(r"\bapi\b|\bdeveloper\b|\bendpoint\b", t):
            parts.append("REST")
        else:
            parts.append("Unknown")
    breadth = "broad" if len(re.findall(r"\bendpoint\b|\bresource\b|\bapi reference\b", t)) >= 3 else "narrow"
    return f"{', '.join(parts)}, {breadth}"


def detect_mcp(text: str) -> str:
    t = _text_lower(text)
    if re.search(r"\bofficial mcp\b|\bmcp server\b.*official", t):
        return "Official MCP server mentioned in docs"
    if re.search(r"\bmcp server\b|\bmodel context protocol\b", t):
        return "Community or third-party MCP servers mentioned"
    return "None official"


def detect_buildable(auth: list, api_surface: str, gating: str, blocker: Optional[str]) -> tuple[str, Optional[str]]:
    if "none (cli" in api_surface.lower() or api_surface.lower().startswith("none"):
        return "blocked", blocker or "No HTTP API surface to wrap as a toolkit"
    if gating == "gated":
        return "blocked", blocker
    if gating == "mixed":
        return "partial", blocker
    return "ready", None


def extract_from_text(app_name: str, page_text: str) -> dict:
    auth = detect_auth(page_text)
    gating, gating_notes, blocker = detect_gating(page_text)
    api_surface = detect_api_surface(page_text, app_name)
    mcp_status = detect_mcp(page_text)
    buildable, b2 = detect_buildable(auth, api_surface, gating, blocker)
    blocker = b2 or blocker
    confidence = "medium" if len(page_text) > 800 else "low"
    return {
        "auth": auth,
        "self_serve": gating,
        "gating_notes": gating_notes,
        "api_surface": api_surface,
        "mcp_status": mcp_status,
        "buildable_verdict": buildable,
        "blocker": blocker,
        "confidence": confidence,
    }
