# 011 - OpenClaw Direct Bookkeeping (Local CLI) - Plan

## Phase 0 - Discovery (no code changes)

- Identify existing parser-first and enrichment entrypoints.
- Identify deterministic rules available for category resolution.
- Define the minimal "needs_llm" condition.

Deliverable:
- Implementation checklist and risk notes.

## Phase 1 - MVP: `/bk` text flow (local CLI)

### 1. CLI skeleton
- Add `app/assistant_cli.py` with subcommands:
  - `bk` (rules-first, optional `--no-llm`)
  - `apply` (write final entries)
  - `undo` (archive pages for last write)

### 2. Deterministic path
- Use parser-first pipeline to extract authoritative fields.
- Run enrichment with `skip_gpt=True` and fill defaults.
- Resolve category using existing allowed categories & YAML mappings where possible.

### 3. needs_llm path
- If required fields (at least `分類`) cannot be resolved:
  - Output `status=needs_llm` with draft JSON.
  - Do not write to Notion.

### 4. Apply
- Accept draft JSON with inferred fields.
- Validate category against allowed set.
- Write entries to Notion using existing repo path.

### 5. Undo
- Store last created page ids in KV with TTL (e.g., 10–30 minutes).
- `undo` archives those pages.

Deliverable:
- Local CLI working end-to-end.

## Phase 2 - OpenClaw integration

- In OpenClaw chat:
  - `/bk ...` triggers CLI `bk --no-llm`.
  - If `needs_llm`, OpenClaw infers and triggers `apply`.
  - If created, OpenClaw returns result with Notion links.

Deliverable:
- Direct-chat bookkeeping works without impacting LINE.

## Phase 3 - Batch receipt processing (optional)

- Add `/bk-receipt` command:
  - For high-volume receipt batches, spawn a subagent on-demand.
  - CLI remains the single write path.

Deliverable:
- Controlled token usage for bulk receipt workflows.

## Phase 4 - Reconciliation reuse (optional)

- Consolidate prior OpenClaw PoC reconciliation scripts into CLI commands:
  - `/cc-import` and `/cc-run`
- Ensure statement OCR/import and reconciliation logic are shared.

Deliverable:
- One codebase for reconciliation logic; no drift between script and production.
