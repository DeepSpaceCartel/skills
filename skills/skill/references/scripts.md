# Using scripts in skills

Condensed from
[agentskills.io/skill-creation/using-scripts](https://agentskills.io/skill-creation/using-scripts).
Skills can instruct agents to run shell commands directly, or bundle
reusable scripts in `scripts/`.

## One-off commands

When an existing package already does the job, reference it directly
in `SKILL.md` — no `scripts/` needed. Several ecosystems auto-resolve
dependencies at runtime:

| Runner | Ships with | Notes |
|---|---|---|
| `uvx` | separate install (part of [uv](https://docs.astral.sh/uv/)) | Fast, caches aggressively — `uvx ruff@0.8.0 check .` |
| `pipx` | separate install | Mature alternative to uvx, broader OS-package-manager availability |
| `npx` | Node.js | `npx eslint@9 --fix .`; pin with `@version` |
| `bunx` | Bun | Drop-in npx equivalent, only when the environment has Bun |
| `deno run` | Deno | `deno run --allow-read npm:eslint@9 -- --fix .`; needs explicit permission flags |
| `go run` | Go | `go run golang.org/x/tools/cmd/goimports@v0.28.0 .`; built in |

Tips: **pin versions** so the command behaves the same over time; state
prerequisites in `SKILL.md` (or the `compatibility` frontmatter field)
rather than assuming the agent's environment has them; and once a
command grows complex enough that it's hard to get right on the first
try, move it into a tested script in `scripts/` instead.

## Referencing scripts from `SKILL.md`

Use relative paths from the skill directory root — the agent resolves
them automatically, including inside `references/*.md`, since it runs
commands from the skill root:

```markdown
## Available scripts
- **`scripts/validate.sh`** — Validates configuration files
- **`scripts/process.py`** — Processes input data

## Workflow
1. Run the validation script:
   \`\`\`bash
   bash scripts/validate.sh "$INPUT_FILE"
   \`\`\`
```

## Self-contained scripts

Bundle a script that declares its own dependencies inline, so the agent
runs it with one command — no separate manifest or install step.

- **Python ([PEP 723](https://peps.python.org/pep-0723/))** — a `# ///
  script` TOML block declares dependencies; run with `uv run
  scripts/extract.py` (or `pipx run`, which also supports PEP 723).
  Pin with [PEP 508](https://peps.python.org/pep-0508/) specifiers
  (`"beautifulsoup4>=4.12,<5"`); constrain with `requires-python`; use
  `uv lock --script` for a full lockfile.
- **Deno** — `npm:`/`jsr:` import specifiers make scripts self-contained
  by default (`import * as cheerio from "npm:cheerio@1.0.0"`); run with
  `deno run scripts/extract.ts`. Packages with native addons may not
  work — prefer ones that ship pre-built binaries.
- **Bun** — auto-installs missing packages at runtime when no
  `node_modules` exists; pin versions in the import path
  (`import * as cheerio from "cheerio@1.0.0"`); run with `bun run
  scripts/extract.ts`. An existing `node_modules` anywhere up the tree
  disables auto-install.
- **Ruby** — `require 'bundler/inline'` with a `gemfile do ... end`
  block declares gems directly in the script; run with `ruby
  scripts/extract.rb`. No lockfile, so pin versions explicitly
  (`gem 'nokogiri', '~> 1.16'`).

## Designing scripts for agentic use

The agent reads stdout/stderr to decide what to do next — a few
choices make that dramatically more reliable:

- **No interactive prompts.** Agents run in non-interactive shells and
  cannot answer TTY prompts or confirmation dialogs — a blocking prompt
  hangs indefinitely. Accept all input via flags, env vars, or stdin,
  and fail with a clear error instead of waiting:
  ```
  Error: --env is required. Options: development, staging, production.
  Usage: python scripts/deploy.py --env staging --tag v1.2.3
  ```
- **Document usage with `--help`.** This is the primary interface an
  agent learns from — description, flags, and examples, kept concise
  since it enters context alongside everything else.
- **Helpful error messages.** State what went wrong, what was expected,
  and what to try (`"Error: --format must be one of: json, csv, table.
  Received: \"xml\""`) — an opaque error wastes a turn.
- **Structured output.** Prefer JSON/CSV/TSV over whitespace-aligned
  text so both the agent and pipeline tools (`jq`, `cut`, `awk`) can
  consume it. Send structured data to stdout, diagnostics
  (progress/warnings) to stderr, so the agent can capture clean output
  while still seeing what happened.
- **Idempotency.** Agents may retry commands — "create if not exists"
  is safer than "create and fail on duplicate."
- **Closed input.** Reject ambiguous input with a clear error rather
  than guessing; use enums and closed sets.
- **`--dry-run`** for destructive or stateful operations.
- **Meaningful, documented exit codes** — distinct codes for distinct
  failure types (not found, invalid args, auth failure), explained in
  `--help`.
- **Predictable output size.** Harnesses often truncate tool output
  past a threshold (10-30K characters). Default to a summary with an
  `--offset`-style way to request more, or require an explicit
  `--output <file>|-` flag when output could be large and isn't
  amenable to pagination.
