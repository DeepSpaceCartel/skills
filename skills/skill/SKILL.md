---
name: skill
description: How to create, structure, and review real Agent Skills (SKILL.md files) per the open Agent Skills specification (https://agentskills.io/) - project-agnostic. Covers required/optional frontmatter fields (name, description, license, compatibility, metadata, allowed-tools), the scripts/references/assets directory conventions, progressive disclosure, writing descriptions that trigger reliably, designing bundled scripts for agentic use, and evaluating a skill's output quality. Use when writing a new SKILL.md, reviewing or debugging an existing skill, deciding what belongs in a skill vs. a reference file, tuning a skill's description so it activates correctly, or adding Agent Skills support to an agent/client.
---

# Agent Skills

A skill is a folder containing, at minimum, a `SKILL.md` file with YAML
frontmatter (`name` and `description`, at minimum) plus Markdown
instructions an agent follows to perform a task. Skills can also bundle
scripts, reference docs, templates, and other resources. The format was
originally developed by Anthropic and released as an open,
implementation-agnostic standard — the real spec lives at
[agentskills.io](https://agentskills.io/).

```
skill-name/
├── SKILL.md      # Required: metadata + instructions
├── scripts/      # Optional: executable code
├── references/   # Optional: documentation
├── assets/       # Optional: templates, resources
└── ...           # Any additional files or directories
```

## The core idea: progressive disclosure

Agents load skills in three tiers, so having many skills installed
doesn't cost context until one is actually used:

| Tier | What's loaded | When | Cost |
|---|---|---|---|
| 1. Catalog | `name` + `description` | Session start, for every skill | ~50-100 tokens/skill |
| 2. Instructions | Full `SKILL.md` body | When the skill activates | < 5000 tokens recommended |
| 3. Resources | `scripts/`, `references/`, `assets/` | Only when the instructions reference them | Varies |

Keep `SKILL.md` itself under ~500 lines. Anything more belongs in a
`references/` file that the body links to and tells the agent when to
read — see [`references/specification.md`](references/specification.md#progressive-disclosure).

## `SKILL.md` frontmatter

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | Max 64 chars. Lowercase letters, digits, hyphens only. No leading/trailing/consecutive hyphens. Must match the parent directory name. |
| `description` | Yes | Max 1024 chars, non-empty. States what the skill does *and* when to use it — this is the entire signal an agent uses to decide whether to activate the skill. |
| `license` | No | License name or reference to a bundled license file. |
| `compatibility` | No | Max 500 chars. Environment requirements (intended product, system packages, network access). Most skills don't need it. |
| `metadata` | No | Arbitrary string-to-string map for client-specific extensions. |
| `allowed-tools` | No | Space-separated, pre-approved tools (experimental; e.g. `Bash(git:*) Read`). |

```markdown
---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---
```

A weak description ("Helps with PDFs.") under-triggers or mis-triggers;
see [`references/descriptions.md`](references/descriptions.md) for how
to write and test one that activates reliably. Everything else in the
frontmatter is fully validated by the [`skills-ref`](https://github.com/agentskills/agentskills/tree/main/skills-ref)
reference library (`skills-ref validate ./my-skill`).

## Where to look

| Reference | Covers |
|---|---|
| [`references/specification.md`](references/specification.md) | The full `SKILL.md` format: frontmatter field rules, body content, `scripts/`/`references/`/`assets/` conventions, file-reference rules, validation |
| [`references/writing-skills.md`](references/writing-skills.md) | Grounding a skill in real expertise, spending context wisely, calibrating how prescriptive to be, reusable content patterns (gotchas, templates, checklists, validation loops) |
| [`references/descriptions.md`](references/descriptions.md) | Writing and testing the `description` field so the skill triggers on the right prompts and not on the wrong ones |
| [`references/evaluating.md`](references/evaluating.md) | Eval-driven iteration: test cases, assertions, grading, and improving a skill from real execution traces |
| [`references/scripts.md`](references/scripts.md) | Bundling and designing scripts (`scripts/`) that agents can run reliably — one-off commands, self-contained dependency declarations, agent-friendly CLI design |
| [`references/client-implementation.md`](references/client-implementation.md) | Building Agent Skills support into an agent or dev tool: discovery, parsing, disclosure, activation, context management |

## Quick orientation

A complete, working skill can be one file under 20 lines:

````markdown
---
name: roll-dice
description: Roll dice using a random number generator. Use when asked to roll a die (d6, d20, etc.), roll dice, or generate a random dice roll.
---

To roll a die, use the following command that generates a random number from 1
to the given number of sides:

```bash
echo $((RANDOM % <sides> + 1))
```

Replace `<sides>` with the number of sides on the die (e.g., 6 for a
standard die, 20 for a d20).
````

At session start the agent sees only `name` + `description` for every
installed skill (**discovery**). When a prompt like "roll a d20" matches
the description, the agent reads the full body into context
(**activation**) and follows it, substituting the requested number of
sides (**execution**).

## Open ecosystem

Agent Skills are supported by a large and growing set of agentic
tools — Claude Code, VS Code/Copilot, Cursor, Gemini CLI, OpenAI Codex,
Amp, Goose, and dozens more — see the
[client showcase](https://agentskills.io/clients) for the current list.
A skill written once, with no client-specific assumptions, works
unmodified across all of them.
