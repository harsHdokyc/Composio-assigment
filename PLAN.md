# Plan: Composio Toolkit Audit (100 apps)

Budget: 6–8 hrs. Grading weight, per the brief: **insight over raw table**, plus a real
verification loop and an honest agent build. This plan is ordered so the things that get
graded hardest happen early, not last.

---

## Phase 0 — Set up (30 min)

1. Get a Composio API key (free tier is enough to query the toolkit index).
2. `pip install composio-core anthropic requests` (or `beautifulsoup4` / `trafilatura`
   for docs-page text extraction if you don't want to hand raw HTML to the LLM).
3. Lock the schema before writing any research code — see `AppRecord` in
   `agent/research_agent.py`. Every app becomes exactly this shape, no exceptions.
   Deciding the schema first is what makes the pattern-analysis step (Phase 3) trivial
   instead of a second research pass.

## Phase 1 — Build the research agent (2–2.5 hrs)

1. **Fast path**: `check_composio_toolkit(app_name)` — if Composio already ships a
   toolkit for this app, most of the graded fields (auth, API breadth, MCP status) are
   already normalized in Composio's own data. This is also a legitimate finding on its
   own: "X% of the 100 are already Composio toolkits" is a pattern worth reporting.
2. **Fallback path**: for apps with no existing toolkit —
   - fetch the docs URL (`requests.get` + text extraction, strip nav/footer)
   - one LLM call per app with a strict JSON-schema prompt (see `EXTRACTION_PROMPT`) —
     temperature 0, "return ONLY JSON," and validate the response actually parses
   - on any failure (404, timeout, malformed JSON), the record status becomes
     `"queued"`, not a guess
3. Log every run (`run_log.jsonl`) — which path an app took and why. You'll want this
   later to explain "where it needed a human" without reconstructing it from memory.
4. Run it across all 100. Expect some real failures — sites that block scrapers,
   apps with no docs at all, apps where the "API" is actually a contact-sales page.
   That's data, not noise.

## Phase 2 — Verify before you analyze (1.5–2 hrs)

This is the part most take-homes skip, and the part the brief explicitly grades. Do it
*before* writing the pattern narrative, or you'll unconsciously write the narrative to
match what the agent said instead of what's true.

1. Pull a random sample (~25 of 100). Weight it toward apps flagged low-confidence.
2. For each sampled app, re-derive 4–5 graded fields (auth, self-serve/gated, API
   surface, verdict, evidence URL) **by going back to the docs directly** — not by
   re-reading the agent's summary. A second independent browsing pass (a fresh LLM call
   with only the raw page, no access to the first pass's answer) works well here if you
   don't want to do all 25 by hand.
3. Score it: `run_verification_pass()` in `agent/verify.py` gives you accuracy overall
   and by field, plus a list of misses with what the agent said vs. what's actually true.
4. **Fix the misses in `results.json` and re-run the same sample.** Report both numbers.
   This before/after delta is the actual proof the loop works — a single "we checked
   and it's 95% accurate" number is much weaker and harder to trust.
5. Common miss patterns worth watching for (found in this run): agent conflates "you
   can start the signup flow yourself" with "self-serve" even when a manual approval
   step waits further down the funnel; agent conflates an easy-to-connect MCP server
   with the full underlying API; agent pattern-matches "has a docs page" into "has an
   API" for tools that are actually just a CLI.

## Phase 3 — Find the patterns (1 hr)

Don't eyeball this — `agent/analyze.py` computes it so the numbers in the page match
the numbers in the data file exactly.

1. Auth method distribution (which scheme dominates — expect OAuth2 + API key to cover
   the large majority; Basic auth should be nearly extinct).
2. Self-serve vs. gated split, overall and by category. This is usually a better
   predictor of buildability than API breadth is.
3. Blocker taxonomy: cluster the free-text blockers into a small number of repeat
   patterns (manual approval token, paid-plan gate, sales contract, no API surface at
   all). The category-level breakdown is often more interesting than the overall split
   — e.g. Finance/Fintech skews gated, Developer/Infra skews self-serve.
4. Write the headline as one or two sentences a reviewer could repeat back after
   reading the page once. If it takes a paragraph to state, it's not a headline yet.

## Phase 4 — Build the page (1.5–2 hrs)

One HTML file, understandable in ~2 minutes, no narration needed. Structure, in the
order a reviewer should hit it:

1. **Hero** — the headline stat + a single visual that makes the scale of the audit
   legible at a glance (this build uses a 100-cell status board, one cell per app,
   color-coded by verdict — literal enough to double as an honest progress indicator
   for the queued rows).
2. **Patterns** — 3–4 clustered findings, stated plainly, with the numbers that back
   them shown as small bar charts, not another data table.
3. **Findings** — the actual skimmable table. Filterable by category. Every row links
   to its evidence URL so a reviewer can spot-check without asking you to.
4. **The agent** — a 4-step pipeline diagram (toolkit lookup → docs fetch → extraction
   → verification), each step tagged agent or human, plus the actual orchestration code
   trimmed to the part that matters (and the two lines that are Composio-SDK
   placeholders, clearly marked).
5. **Verification** — pass-1 vs. pass-2 accuracy side by side, and the actual misses
   listed with what was wrong and why, not just a summary percentage.
6. Footer with repo link. No conclusion section — the hero already stated the headline.

Design constraints that matter for a technical reviewer specifically: every color used
should mean something (status, not decoration), the evidence links should be real and
clickable, and the "queued" state should look intentional, not like an unfinished demo.

## Phase 5 — Package (30 min)

1. Deploy the HTML (any static host — Vercel/Netlify/GitHub Pages all work for a
   single file).
2. Push the repo with this plan, the pipeline, and a README that states plainly how to
   run it against all 100 once a live Composio key is available.
3. Sanity-read the whole page once as if you were the reviewer with two minutes and no
   context. If any section makes you want to add a sentence of narration to explain
   it, that section isn't finished yet.
