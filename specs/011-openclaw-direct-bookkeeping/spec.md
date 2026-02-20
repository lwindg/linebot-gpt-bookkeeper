# 011 - OpenClaw Direct Bookkeeping (Local CLI)

## Summary

This spec introduces a new **OpenClaw direct-chat** bookkeeping entrypoint that reuses the existing `linebot-gpt-bookkeeper` logic **locally**.

- **LINE bot path remains unchanged** (Vercel + existing OpenAI inference + Notion write path).
- When the user chats directly with OpenClaw and sends `/bk ...`, OpenClaw triggers a local CLI (via `uv`) to parse, classify (rules-first), and write to Notion.
- LLM inference is used **only as a fallback** when deterministic rules cannot resolve the required fields.
- **Single source of truth for writes:** Notion writes must go through the repo code path (CLI) to prevent schema drift.

## Goals

- Provide a reliable, low-friction way to create ledger entries from OpenClaw chat using the same project rules.
- Keep LINE UX/behavior stable.
- Keep costs predictable by using deterministic parsing/rules first.
- Prevent logic duplication between OpenClaw scripts/PoCs and the production repo.

## Non-goals

- Do not replace the LINE bot inference stack.
- Do not introduce a long-running service.
- Do not redesign Notion schemas.

## Key Decisions

### Command trigger
- OpenClaw direct-chat uses **explicit commands only**.
  - Primary: `/bk <text>`
  - Optional later: `/bk-receipt`, `/cc-import`, `/cc-run`

### Policy
- **1B (direct write)**: For `/bk`, do not require a pre-"OK" confirmation step.
- **2A (rules-first)**: Use deterministic parsing and rules/lexicons first.
- **Fallback inference**: If required fields cannot be resolved deterministically, OpenClaw performs inference and then re-invokes CLI for applying the result.

### Single write path
- CLI uses existing repo Notion write logic (e.g., `NotionService` / `send_to_webhook()` when `USE_NOTION_API=true`).
- OpenClaw never writes to Notion directly for `/bk` to avoid dual mappings.

### User identity
- Use the user's LINE `user_id` when invoking CLI to reuse existing KV lock keys.
- For the initial implementation, use:
  - `Uf20daa11f764b7d19e69db3d49ba9f2e`

## Functional Requirements

### FR-1: Local CLI entrypoint
- Provide a CLI module runnable via:
  - `uv run python -m app.assistant_cli ...`

### FR-2: `/bk` text bookkeeping
- Input: single-line natural language bookkeeping text.
- Output: created Notion pages (via repo write path) OR `needs_llm` draft.

### FR-3: No-LLM mode in CLI
- CLI must support a `--no-llm` mode that:
  - Never calls OpenAI.
  - Returns `needs_llm` with a structured draft when resolution is incomplete.

### FR-4: Apply flow
- After OpenClaw fills required fields, CLI `apply` writes the final entry to Notion.

### FR-5: Undo
- Because `/bk` writes without a pre-confirm, provide an undo mechanism.
- Prefer archiving pages rather than hard delete.

## Data Contract (JSON)

### `bk` output

- `status=created`:

```json
{
  "status": "created",
  "result": {
    "transaction_id": "...",
    "created_pages": [{"page_id":"...","url":"..."}],
    "count": 1
  }
}
```

- `status=needs_llm`:

```json
{
  "status": "needs_llm",
  "draft": {
    "user_id": "Uf20...",
    "source_text": "買東西 300 現金",
    "entries": [
      {
        "日期": "YYYY-MM-DD",
        "品項": "...",
        "原幣別": "TWD",
        "原幣金額": 300,
        "付款方式": "現金",
        "交易類型": "支出",
        "分類": null,
        "必要性": null,
        "明細說明": ""
      }
    ]
  }
}
```

### `apply` input
- `apply` accepts `draft_json` that includes the inferred fields (e.g., `分類`).

## Open Questions

1) Undo behavior: archive vs hard delete (recommend archive).
2) Transaction id strategy: reuse existing generator vs add prefix `openclaw-...` for traceability.
3) Receipt & reconciliation CLI commands scope and timing.
