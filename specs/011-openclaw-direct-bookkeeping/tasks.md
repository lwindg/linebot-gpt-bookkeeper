# 011 - OpenClaw Direct Bookkeeping (Local CLI) - Tasks

> Language: spec/communication in zh-TW, code/commit messages in English.

## Phase 0 - Discovery

- [ ] Audit parser-first entrypoints usable from CLI.
- [ ] Identify minimal deterministic category resolution path (no OpenAI).
- [ ] Define `needs_llm` conditions.

## Phase 1 - MVP CLI

- [ ] Add `app/assistant_cli.py` with subcommands: `bk`, `apply`, `undo`.
- [ ] Implement `bk --no-llm`:
  - [ ] Parse input via parser-first pipeline.
  - [ ] Enrich with `skip_gpt=True`.
  - [ ] Resolve category via YAML mappings / allowed categories.
  - [ ] If unresolved -> output `needs_llm` draft JSON.
  - [ ] If resolved -> write to Notion via repo write path.
- [ ] Implement `apply`:
  - [ ] Validate inferred fields.
  - [ ] Write to Notion.
- [ ] Implement `undo`:
  - [ ] Store last created pages in KV with TTL.
  - [ ] Archive last created pages.

## Phase 2 - OpenClaw chat integration

- [ ] Add OpenClaw command handler for `/bk ...` that runs local CLI.
- [ ] Handle `needs_llm` by having OpenClaw infer and call `apply`.

## Optional

- [ ] Batch receipts with on-demand subagent (`/bk-receipt`).
- [ ] Consolidate reconciliation PoC into repo CLI (`/cc-import`, `/cc-run`).

## Open Questions

- [ ] Undo: archive vs hard delete (recommend archive).
- [ ] Transaction id strategy: reuse existing generator vs prefix `openclaw-`.
