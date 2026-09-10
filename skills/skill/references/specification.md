# The `SKILL.md` specification

The complete, real format spec lives at
[agentskills.io/specification](https://agentskills.io/specification).
This is the condensed version.

## Directory structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md      # Required: metadata + instructions
├── scripts/      # Optional: executable code
├── references/   # Optional: documentation
├── assets/       # Optional: templates, resources
└── ...           # Any additional files or directories
```

`SKILL.md` must contain YAML frontmatter followed by Markdown content.

## Frontmatter fields

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | Max 64 chars. |
| `description` | Yes | Max 1024 chars, non-empty. |
| `license` | No | License name, or the name of a bundled license file. |
| `compatibility` | No | Max 500 chars. |
| `metadata` | No | String-to-string map. |
| `allowed-tools` | No | Space-separated tool list. Experimental — support varies by client. |

### `name`

- 1-64 characters.
- Only unicode lowercase alphanumerics (`a-z`, `0-9`) and hyphens.
- Must not start or end with a hyphen, and no consecutive hyphens
  (`pdf--processing` is invalid).
- Must match the parent directory name.

### `description`

- 1-1024 characters.
- Should describe both *what* the skill does and *when* to use it —
  this is the only signal an agent has to decide whether to activate
  the skill (see [`descriptions.md`](descriptions.md)).
- Include specific keywords an agent can match against a real task.

```yaml
# Good
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.

# Poor — too vague to trigger reliably
description: Helps with PDFs.
```

### `license`

Keep it short: either a license identifier or the name of a bundled
license file (e.g. `Proprietary. LICENSE.txt has complete terms`).

### `compatibility`

Only include this when the skill has real environment requirements —
an intended product, required system packages, network access. Most
skills don't need it.

```yaml
compatibility: Requires git, docker, jq, and access to the internet
```

### `metadata`

A string-to-string map for client-specific extensions the spec doesn't
define. Use reasonably unique key names to avoid collisions across
clients.

```yaml
metadata:
  author: example-org
  version: "1.0"
```

### `allowed-tools`

A space-separated string of tools pre-approved to run without prompting
the user. Experimental; support varies across agent implementations.

```yaml
allowed-tools: Bash(git:*) Bash(jq:*) Read
```

## Body content

The Markdown after the frontmatter has no format restrictions — write
whatever helps the agent perform the task. Useful sections: step-by-step
instructions, input/output examples, common edge cases. Remember the
whole body loads into context once activated — split long content into
referenced files rather than growing `SKILL.md` indefinitely.

## Optional directories

Beyond `SKILL.md`, a skill directory may hold anything. These are
recommended conventions, not requirements:

- **`scripts/`** — executable code the agent can run. Self-contained or
  clearly documents its own dependencies; helpful error messages;
  handles edge cases. See [`scripts.md`](scripts.md).
- **`references/`** — additional documentation loaded on demand
  (`REFERENCE.md`, domain-specific files like `finance.md`). Keep
  individual files focused — smaller files mean less wasted context
  when the agent loads one.
- **`assets/`** — static resources: templates, images, data files,
  lookup tables, schemas.

## Progressive disclosure

Skills load in three tiers so many installed skills stay cheap until
used:

1. **Metadata** (~100 tokens) — `name` + `description`, loaded at
   startup for every skill.
2. **Instructions** (< 5000 tokens recommended) — the full `SKILL.md`
   body, loaded once the skill activates.
3. **Resources** — files under `scripts/`, `references/`, `assets/`,
   loaded only as the instructions reference them.

Keep `SKILL.md` under ~500 lines; move detail to separate files.

## File references

Reference other bundled files with **relative paths from the skill
root** — the agent resolves these automatically:

```markdown
See [the reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py
```

Keep references one level deep from `SKILL.md` — avoid chains where a
reference file points to another reference file that points to a third.

## Validation

Validate frontmatter and naming conventions with the
[`skills-ref`](https://github.com/agentskills/agentskills/tree/main/skills-ref)
reference library:

```bash
skills-ref validate ./my-skill
```
