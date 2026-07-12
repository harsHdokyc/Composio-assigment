"""Generate output/case-study.html from pipeline JSON (no pre-existing HTML required)."""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
OUT_DIR = ROOT / "output"
OUT = OUT_DIR / "case-study.html"
ROOT_COPY = ROOT / "case-study.html"


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def pct(n, total):
    return 0 if not total else round(100 * n / total)


def bar_rows(dist: dict, color: str, max_n: int | None = None) -> str:
    if not dist:
        return "<p style='font-size:13px;color:var(--ink-soft)'>No data yet.</p>"
    peak = max_n or max(dist.values()) or 1
    rows = []
    for label, count in list(dist.items())[:6]:
        width = min(100, round(100 * count / peak))
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{label}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width}%;background:{color}"></div></div>'
            f'<span class="bar-val">{count}</span></div>'
        )
    return "\n".join(rows)


def blocker_lines(top_blockers: dict) -> str:
    if not top_blockers:
        return "<p style='font-size:13px;color:var(--ink-soft);margin:0'>No blockers recorded.</p>"
    lines = []
    for text, count in list(top_blockers.items())[:5]:
        lines.append(f'<p style="font-size:12.5px;margin:0 0 6px;">→ {text} <span class="mono">({count})</span></p>')
    return "\n".join(lines)


def main():
    apps = load("apps.json")
    results = load("results.json")
    analysis = load("analysis.json")
    verification = load("verification_log.json")

    bundle = {
        "apps": apps,
        "results": results,
        "analysis": analysis,
        "verification": verification,
    }
    (DATA / "bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    meta = results["meta"]
    researched = meta.get("researched", 0)
    total = meta.get("total_apps", len(apps))
    gating = analysis.get("gating_distribution", {})
    auth = analysis.get("auth_distribution", {})
    self_serve = gating.get("self-serve", 0)
    self_serve_pct = pct(self_serve, analysis.get("sample_size") or researched or 1)

    p1 = verification.get("pass_1", {})
    p2 = verification.get("pass_2", {})
    p1_acc = p1.get("accuracy_pct", 0)
    p2_acc = p2.get("accuracy_pct", 0)
    miss_count = len(p1.get("misses", []))

    headline = analysis.get("headline", "")
    payload = json.dumps(bundle, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Toolkit Audit — 100 Apps, Agent-Researched</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --ink:#12151a; --ink-soft:#4a4f58; --paper:#f5f6f4; --paper-raised:#ffffff;
    --line:#dcdfd9; --accent:#2c4bd4; --accent-soft:#e7ecff;
    --ok:#1f8a56; --ok-soft:#e3f5eb; --warn:#b5790a; --warn-soft:#fbf0dc;
    --bad:#c13d3d; --bad-soft:#fbe6e6; --queued:#9a9d97; --queued-soft:#e9eae7;
  }}
  *{{box-sizing:border-box;}}
  html{{scroll-behavior:smooth;}}
  body{{margin:0;background:var(--paper);color:var(--ink);font-family:'IBM Plex Sans',sans-serif;font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased;}}
  h1,h2,h3{{font-family:'Space Grotesk',sans-serif;letter-spacing:-0.01em;}}
  .mono{{font-family:'IBM Plex Mono',monospace;}}
  a{{color:var(--accent);}}
  .wrap{{max-width:1180px;margin:0 auto;padding:0 32px;}}
  @media (max-width:700px){{.wrap{{padding:0 18px;}}}}
  .topbar{{position:sticky;top:0;z-index:50;background:rgba(245,246,244,0.92);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);}}
  .topbar-inner{{max-width:1180px;margin:0 auto;padding:14px 32px;display:flex;align-items:center;justify-content:space-between;}}
  .brand{{font-family:'Space Grotesk';font-weight:600;font-size:15px;}}
  .brand span{{color:var(--accent);}}
  .topnav{{display:flex;gap:22px;font-size:13px;}}
  .topnav a{{color:var(--ink-soft);text-decoration:none;}}
  .topnav a:hover{{color:var(--ink);}}
  @media (max-width:700px){{.topnav{{display:none;}}}}
  .hero{{padding:64px 0 40px;}}
  .eyebrow{{font-family:'IBM Plex Mono';font-size:12px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:18px;display:flex;align-items:center;gap:10px;}}
  .eyebrow::before{{content:"";width:22px;height:1px;background:var(--ink-soft);}}
  h1{{font-size:44px;font-weight:600;line-height:1.08;margin:0 0 20px;max-width:780px;}}
  h1 em{{font-style:normal;color:var(--accent);}}
  .hero-sub{{font-size:17px;color:var(--ink-soft);max-width:620px;margin:0 0 36px;}}
  @media (max-width:700px){{h1{{font-size:30px;}}}}
  .hero-grid{{display:grid;grid-template-columns:1.1fr 1fr;gap:48px;align-items:start;}}
  @media (max-width:900px){{.hero-grid{{grid-template-columns:1fr;}}}}
  .stat-row{{display:flex;gap:28px;flex-wrap:wrap;margin-bottom:34px;}}
  .stat .num{{font-family:'Space Grotesk';font-size:34px;font-weight:600;line-height:1;}}
  .stat .lbl{{font-size:12.5px;color:var(--ink-soft);margin-top:6px;max-width:140px;}}
  .board-card{{background:var(--paper-raised);border:1px solid var(--line);border-radius:10px;padding:22px;}}
  .board-title{{font-size:13px;font-weight:600;margin-bottom:3px;}}
  .board-caption{{font-size:12.5px;color:var(--ink-soft);margin-bottom:16px;}}
  .board{{display:grid;grid-template-columns:repeat(10,1fr);gap:4px;}}
  .cell{{aspect-ratio:1;border-radius:3px;position:relative;}}
  .cell.ready{{background:var(--ok);}}
  .cell.partial{{background:var(--warn);}}
  .cell.blocked{{background:var(--bad);}}
  .cell.queued{{background:var(--queued-soft);border:1px dashed var(--queued);}}
  .cell:hover::after{{content:attr(data-name);position:absolute;bottom:120%;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;font-family:'IBM Plex Mono';font-size:10.5px;padding:4px 7px;border-radius:4px;white-space:nowrap;z-index:10;}}
  .board-legend{{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;font-size:11.5px;color:var(--ink-soft);}}
  .board-legend span{{display:inline-flex;align-items:center;gap:6px;}}
  .swatch{{width:9px;height:9px;border-radius:2px;display:inline-block;}}
  section{{padding:52px 0;border-top:1px solid var(--line);}}
  .section-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:28px;flex-wrap:wrap;}}
  .section-tag{{font-family:'IBM Plex Mono';font-size:12px;color:var(--accent);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;}}
  h2{{font-size:26px;font-weight:600;margin:0;}}
  .section-note{{font-size:14px;color:var(--ink-soft);max-width:360px;}}
  .pattern-lead{{font-size:19px;line-height:1.55;max-width:820px;margin-bottom:36px;}}
  .card-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
  @media (max-width:820px){{.card-grid{{grid-template-columns:1fr;}}}}
  .pcard{{background:var(--paper-raised);border:1px solid var(--line);border-radius:10px;padding:20px;}}
  .pcard .ptitle{{font-size:13px;color:var(--ink-soft);margin-bottom:10px;}}
  .bar-row{{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:13px;}}
  .bar-label{{width:92px;flex-shrink:0;color:var(--ink-soft);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
  .bar-track{{flex:1;height:8px;background:var(--paper);border-radius:4px;overflow:hidden;}}
  .bar-fill{{height:100%;border-radius:4px;}}
  .bar-val{{width:34px;text-align:right;font-family:'IBM Plex Mono';font-size:12px;flex-shrink:0;}}
  .filters{{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap;}}
  .chip{{font-family:'IBM Plex Mono';font-size:12px;padding:6px 12px;border-radius:20px;border:1px solid var(--line);background:var(--paper-raised);cursor:pointer;color:var(--ink-soft);}}
  .chip.active{{background:var(--ink);color:#fff;border-color:var(--ink);}}
  table{{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--paper-raised);border:1px solid var(--line);border-radius:10px;overflow:hidden;}}
  thead th{{text-align:left;font-family:'IBM Plex Mono';font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:0.04em;color:var(--ink-soft);padding:12px 14px;border-bottom:1px solid var(--line);background:var(--paper);}}
  tbody td{{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top;}}
  tbody tr:last-child td{{border-bottom:none;}}
  tbody tr:hover{{background:var(--paper);}}
  .tag{{display:inline-block;font-family:'IBM Plex Mono';font-size:11px;padding:2px 8px;border-radius:20px;}}
  .tag.ready{{background:var(--ok-soft);color:var(--ok);}}
  .tag.partial{{background:var(--warn-soft);color:var(--warn);}}
  .tag.blocked{{background:var(--bad-soft);color:var(--bad);}}
  .tag.unknown,.tag.queued{{background:var(--queued-soft);color:var(--queued);}}
  .gate-dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;}}
  .gate-dot.self-serve{{background:var(--ok);}}
  .gate-dot.mixed{{background:var(--warn);}}
  .gate-dot.gated{{background:var(--bad);}}
  .gate-dot.unknown{{background:var(--queued);}}
  .ev-link{{font-family:'IBM Plex Mono';font-size:11.5px;}}
  .app-name{{font-weight:600;}}
  .app-cat{{display:block;font-size:11px;color:var(--ink-soft);margin-top:1px;}}
  .pipeline{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin-bottom:36px;}}
  @media (max-width:820px){{.pipeline{{grid-template-columns:1fr;}}}}
  .pstep{{border:1px solid var(--line);background:var(--paper-raised);padding:20px;}}
  .pstep:not(:last-child){{border-right:none;}}
  @media (max-width:820px){{.pstep:not(:last-child){{border-right:1px solid var(--line);}}}}
  .pstep .pnum{{font-family:'IBM Plex Mono';font-size:11px;color:var(--accent);margin-bottom:8px;}}
  .pstep h3{{font-size:15px;margin:0 0 8px;}}
  .pstep p{{font-size:13px;color:var(--ink-soft);margin:0;}}
  .pstep .who{{margin-top:12px;display:inline-block;font-family:'IBM Plex Mono';font-size:10.5px;padding:2px 8px;border-radius:20px;}}
  .who.agent{{background:var(--accent-soft);color:var(--accent);}}
  .who.human{{background:var(--warn-soft);color:var(--warn);}}
  .code-block{{background:#171a20;color:#dfe3e8;border-radius:10px;padding:20px 22px;font-family:'IBM Plex Mono';font-size:12.5px;line-height:1.7;overflow-x:auto;}}
  .code-block .c1{{color:#7fb0ff;}} .code-block .c2{{color:#93d0a5;}} .code-block .c3{{color:#8a8f98;}}
  .verify-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:30px;}}
  @media (max-width:820px){{.verify-grid{{grid-template-columns:1fr;}}}}
  .accuracy-card{{background:var(--paper-raised);border:1px solid var(--line);border-radius:10px;padding:24px;text-align:center;}}
  .accuracy-card .num{{font-family:'Space Grotesk';font-size:46px;font-weight:700;}}
  .accuracy-card.pass1 .num{{color:var(--warn);}}
  .accuracy-card.pass2 .num{{color:var(--ok);}}
  .accuracy-card .lbl{{font-size:12.5px;color:var(--ink-soft);margin-top:6px;}}
  .miss-row{{display:grid;grid-template-columns:140px 1fr 1fr;gap:16px;padding:14px 16px;border-bottom:1px solid var(--line);font-size:13px;}}
  .miss-row:last-child{{border-bottom:none;}}
  .miss-row .who{{font-weight:600;}}
  .miss-row .was{{color:var(--bad);}}
  .miss-row .now{{color:var(--ok);}}
  .miss-note{{grid-column:1 / -1;font-size:12px;color:var(--ink-soft);margin-top:2px;}}
  .miss-wrap{{background:var(--paper-raised);border:1px solid var(--line);border-radius:10px;overflow:hidden;}}
  footer{{padding:36px 0 60px;font-size:12.5px;color:var(--ink-soft);}}
  .cta-row{{display:flex;gap:12px;flex-wrap:wrap;margin-top:8px;}}
  .btn{{font-family:'IBM Plex Mono';font-size:12.5px;padding:9px 16px;border-radius:8px;text-decoration:none;display:inline-flex;align-items:center;gap:8px;}}
  .btn.primary{{background:var(--ink);color:#fff;}}
  .btn.ghost{{border:1px solid var(--line);color:var(--ink);}}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-inner">
    <div class="brand">toolkit-audit <span>/ 100</span></div>
    <div class="topnav">
      <a href="#patterns">Patterns</a>
      <a href="#findings">Findings</a>
      <a href="#agent">Agent</a>
      <a href="#verification">Verification</a>
    </div>
  </div>
</div>
<div class="wrap">
  <section class="hero" style="border-top:none;">
    <div class="eyebrow">AI Product Ops — take-home — Composio</div>
    <h1>Before you build a toolkit, you have to know<br><em>who's actually letting you in.</em></h1>
    <p class="hero-sub">100 apps researched for auth, access, and API surface via the Composio API + docs heuristics. This page is the whole submission: findings, patterns, the pipeline, and verification accuracy.</p>
    <div class="hero-grid">
      <div>
        <div class="stat-row">
          <div class="stat"><div class="num">{researched} / {total}</div><div class="lbl">apps researched in this run</div></div>
          <div class="stat"><div class="num">{self_serve_pct}%</div><div class="lbl">of researched apps are self-serve</div></div>
          <div class="stat"><div class="num">{p1_acc}% → {p2_acc}%</div><div class="lbl">sample accuracy, before and after verification</div></div>
        </div>
        <div class="cta-row">
          <a class="btn primary" href="#agent">See the pipeline ↓</a>
          <a class="btn ghost" href="#verification">See the accuracy check ↓</a>
        </div>
      </div>
      <div class="board-card">
        <div class="board-title">All 100 apps, one board</div>
        <div class="board-caption">Green = ready, amber = partial, red = blocked, hollow = queued. Hover a cell.</div>
        <div class="board" id="board"></div>
        <div class="board-legend">
          <span><span class="swatch" style="background:var(--ok)"></span>ready</span>
          <span><span class="swatch" style="background:var(--warn)"></span>partial</span>
          <span><span class="swatch" style="background:var(--bad)"></span>blocked</span>
          <span><span class="swatch" style="background:var(--queued-soft);border:1px dashed var(--queued)"></span>queued</span>
        </div>
      </div>
    </div>
  </section>

  <section id="patterns">
    <div class="section-tag">01 — the headline</div>
    <div class="section-head"><h2>The pattern isn't auth. It's who's on the other end of the gate.</h2></div>
    <p class="pattern-lead">{headline}</p>
    <div class="card-grid">
      <div class="pcard">
        <div class="ptitle">Auth methods, researched sample</div>
        {bar_rows(auth, "var(--accent)")}
      </div>
      <div class="pcard">
        <div class="ptitle">Gating, researched sample</div>
        {bar_rows(gating, "var(--ok)")}
      </div>
      <div class="pcard">
        <div class="ptitle">Top blockers</div>
        {blocker_lines(analysis.get("top_blockers", {}))}
      </div>
    </div>
  </section>

  <section id="findings">
    <div class="section-tag">02 — the findings</div>
    <div class="section-head">
      <h2>{researched} apps researched</h2>
      <p class="section-note">Filter by category. Every row links to its evidence URL.</p>
    </div>
    <div class="filters" id="filters"></div>
    <table id="findings-table">
      <thead><tr><th>App</th><th>Auth</th><th>Access</th><th>API surface</th><th>Verdict</th><th>Evidence</th></tr></thead>
      <tbody id="findings-body"></tbody>
    </table>
  </section>

  <section id="agent">
    <div class="section-tag">03 — the agent</div>
    <div class="section-head">
      <h2>What ran on its own, and where verification stepped in</h2>
      <p class="section-note">Research, analysis, and verification are separate scripts so each is easy to audit.</p>
    </div>
    <div class="pipeline">
      <div class="pstep"><div class="pnum">01</div><h3>Toolkit lookup</h3><p>Query Composio's toolkit catalog. If the app exists, auth and API surface come from structured metadata.</p><span class="who agent">agent</span></div>
      <div class="pstep"><div class="pnum">02</div><h3>Docs fetch + extract</h3><p>Fetch the docs URL, run rule-based heuristics for gating, surface, and buildable verdict.</p><span class="who agent">agent</span></div>
      <div class="pstep"><div class="pnum">03</div><h3>Sample cross-check</h3><p>Re-fetch a held-out sample independently and compare against the agent output.</p><span class="who human">verify</span></div>
      <div class="pstep"><div class="pnum">04</div><h3>Correct &amp; re-score</h3><p>Misses get fixed in results.json and re-flagged verified. Pattern analysis runs last.</p><span class="who human">verify</span></div>
    </div>
    <div class="code-block">
<span class="c3"># research_agent.py — orchestration loop</span><br>
<span class="c1">def</span> research_app(app):<br>
&nbsp;&nbsp;hit = check_composio_toolkit(app)&nbsp;&nbsp;<span class="c3"># COMPOSIO API</span><br>
&nbsp;&nbsp;<span class="c1">if</span> hit: record.update(hit)<br>
&nbsp;&nbsp;page = fetch_docs_page(docs_url)&nbsp;&nbsp;<span class="c3"># HTTP fetch</span><br>
&nbsp;&nbsp;record.update(extract_from_text(app[<span class="c2">"name"</span>], page))<br>
&nbsp;&nbsp;<span class="c1">return</span> record
    </div>
  </section>

  <section id="verification">
    <div class="section-tag">04 — verification</div>
    <div class="section-head">
      <h2>Where the agent was right, and where it wasn't</h2>
      <p class="section-note">{p1.get("sample_size", 0)} field-level checks, scored against a fresh docs re-fetch.</p>
    </div>
    <div class="verify-grid">
      <div class="accuracy-card pass1"><div class="num">{p1_acc}%</div><div class="lbl">pass 1 — agent draft, unreviewed ({miss_count} misses)</div></div>
      <div class="accuracy-card pass2"><div class="num">{p2_acc}%</div><div class="lbl">pass 2 — after misses were corrected</div></div>
    </div>
    <div class="miss-wrap" id="miss-wrap"></div>
  </section>
</div>
<footer>
  <div class="wrap">Built for the Composio AI Product Ops take-home · Queued rows are not guesses — they're the honest remainder of a 100-app run.</div>
</footer>
<script>
const DATA = {payload};
const board = document.getElementById('board');
const resultsById = {{}};
DATA.results.apps.forEach(r => resultsById[r.id] = r);
DATA.apps.forEach(app => {{
  const r = resultsById[app.id];
  const cell = document.createElement('div');
  let cls = 'queued';
  if (r) {{
    const v = r.buildable_verdict;
    cls = (v === 'ready' || v === 'partial' || v === 'blocked') ? v : 'queued';
  }}
  cell.className = 'cell ' + cls;
  cell.setAttribute('data-name', app.name + (r && r.research_status !== 'queued' ? '' : ' (queued)'));
  board.appendChild(cell);
}});
const tbody = document.getElementById('findings-body');
const filtersEl = document.getElementById('filters');
const researchedApps = DATA.results.apps.filter(a => a.research_status !== 'queued');
const categories = ['All', ...new Set(researchedApps.map(a => a.category))];
let activeCat = 'All';
function renderChips(){{
  filtersEl.innerHTML = '';
  categories.forEach(cat => {{
    const chip = document.createElement('div');
    chip.className = 'chip' + (cat === activeCat ? ' active' : '');
    chip.textContent = cat;
    chip.onclick = () => {{ activeCat = cat; renderChips(); renderTable(); }};
    filtersEl.appendChild(chip);
  }});
}}
function renderTable(){{
  tbody.innerHTML = '';
  researchedApps.filter(a => activeCat === 'All' || a.category === activeCat).forEach(a => {{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="app-name">${{a.name}}</span><span class="app-cat">${{a.category}}</span></td>
      <td class="mono" style="font-size:12px;">${{(a.auth || []).join(', ') || '—'}}</td>
      <td><span class="gate-dot ${{a.self_serve}}"></span>${{a.self_serve}}</td>
      <td style="font-size:12.5px;max-width:220px;">${{a.api_surface || '—'}}</td>
      <td><span class="tag ${{a.buildable_verdict}}">${{a.buildable_verdict}}</span></td>
      <td>${{a.evidence_url ? `<a class="ev-link" href="${{a.evidence_url}}" target="_blank" rel="noopener">docs ↗</a>` : '—'}}</td>`;
    tbody.appendChild(tr);
  }});
}}
renderChips();
renderTable();
const missWrap = document.getElementById('miss-wrap');
(DATA.verification.pass_1.misses || []).forEach(m => {{
  const row = document.createElement('div');
  row.className = 'miss-row';
  row.innerHTML = `
    <div class="who">${{m.app}}<br><span style="font-weight:400;color:var(--ink-soft);font-size:11.5px;">${{m.field}}</span></div>
    <div class="was">✕ ${{m.agent_said}}</div>
    <div class="now">✓ ${{m.actually}}</div>
    <div class="miss-note">${{m.note || ''}}</div>`;
  missWrap.appendChild(row);
}});
</script>
</body>
</html>
"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    ROOT_COPY.write_text(html, encoding="utf-8")
    print(f"Built {OUT} — {researched}/{total} researched")


if __name__ == "__main__":
    main()
