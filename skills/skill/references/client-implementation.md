# Adding Agent Skills support to a client

Condensed from
[agentskills.io/client-implementation/adding-skills-support](https://agentskills.io/client-implementation/adding-skills-support).
For building Agent Skills support into an agent or dev tool, not for
authoring individual skills. Two things vary by architecture: where
skills live (local filesystem scan vs. a cloud/sandboxed agent needing
an API, registry, or bundled assets) and how the model accesses skill
content (direct file reads vs. a dedicated tool or prompt injection).

## The core principle: progressive disclosure

| Tier | What's loaded | When | Cost |
|---|---|---|---|
| 1. Catalog | `name` + `description` | Session start | ~50-100 tokens/skill |
| 2. Instructions | Full `SKILL.md` body | On activation | < 5000 tokens recommended |
| 3. Resources | Scripts, references, assets | When instructions reference them | Varies |

## Step 1: Discover skills

Scan at least **project-level** (relative to the working directory) and
**user-level** (relative to home) scopes; organization-wide or
bundled-with-the-agent scopes are also common. Within each scope, scan
both your client's own directory and the cross-client
`.agents/skills/` convention:

| Scope | Path | Purpose |
|---|---|---|
| Project | `<project>/.<your-client>/skills/` | Client-native location |
| Project | `<project>/.agents/skills/` | Cross-client interop |
| User | `~/.<your-client>/skills/` | Client-native location |
| User | `~/.agents/skills/` | Cross-client interop |

The spec doesn't mandate where skills live — only what's inside them —
but scanning `.agents/skills/` means skills installed for other
compliant clients are automatically visible to yours. (`.claude/skills/`
is also worth scanning pragmatically, since many existing skills live
there.) Also consider ancestor directories up to the git root
(monorepos), XDG config dirs, and user-configured paths.

Within a skills directory, look for subdirectories containing a file
named exactly `SKILL.md`; skip `.git/`, `node_modules/`, optionally
respect `.gitignore`, and bound scan depth/directory count to avoid
runaway scans.

**Collisions:** when two skills share a `name`, apply a deterministic
rule — the universal convention is **project-level overrides
user-level**. Within the same scope, first-found or last-found both
work; pick one, log a warning when it happens.

**Trust:** project-level skills come from the repo being worked on,
which may be untrusted (a freshly cloned repo). Consider gating
project-level skill loading on a trust check so an untrusted repo can't
silently inject instructions into the agent's context.

**Cloud/sandboxed agents** without local filesystem access: project-
level skills can still travel with a cloned repo; user/org-level skills
need external provisioning (a config repo, uploaded skill packages);
built-in skills can ship as static assets in the deployment artifact.

## Step 2: Parse `SKILL.md`

Split on the YAML frontmatter delimiters (`---` ... `---`); parse
`name`/`description` (required) plus any optional fields; everything
after the closing `---`, trimmed, is the body.

**Malformed YAML:** skills authored for other clients sometimes have
technically-invalid YAML their parser happened to accept — most
commonly an unquoted value containing a colon
(`description: Use this skill when: the user asks about PDFs`).
Consider a fallback that quotes such values before retrying, for
cross-client compatibility.

**Lenient validation** — warn but still load where possible:
- Name doesn't match parent directory → warn, load anyway.
- Name > 64 chars → warn, load anyway.
- Description missing/empty → skip the skill, log the error (a
  description is essential for disclosure).
- YAML unparseable → skip the skill, log the error.

**Store, per skill:** `name`, `description`, `location` (absolute path
to `SKILL.md`), keyed by `name` for fast lookup. The body can be cached
at discovery time (faster activation) or read at activation time (lower
aggregate memory, picks up file changes). Derive the skill's base
directory from `location` to resolve relative paths later.

## Step 3: Disclose the catalog

Include `name` + `description` (+ optionally `location`) for every
discovered skill in a compact structured format:

```xml
<available_skills>
  <skill>
    <name>pdf-processing</name>
    <description>Extract PDF text, fill forms, merge files. Use when handling PDFs.</description>
    <location>/home/user/.agents/skills/pdf-processing/SKILL.md</location>
  </skill>
</available_skills>
```

Place it either in the **system prompt** (simplest, works with any
model that has file-read access) or embedded in a **dedicated
activation tool's description** (keeps the system prompt clean, couples
discovery with activation). Pair it with a short instruction block
telling the model how to activate a skill (via file-read, or via the
tool) — keep this concise; the skill content itself carries the detail.

**Filtering:** hide disabled/denied/opted-out skills from the catalog
entirely rather than listing and blocking them at activation — this
stops the model wasting turns on skills it can't use. If no skills are
discovered, omit the catalog and instruction block entirely rather than
showing an empty block.

## Step 4: Activate skills

**Model-driven** (the common case): the model reads the catalog,
judges relevance, and loads the skill — no harness-side keyword
matching needed.

- **File-read activation** — the model calls its normal file-read tool
  on the `SKILL.md` path from the catalog. Needs no special
  infrastructure.
- **Dedicated tool activation** (`activate_skill(name)`) — required
  when the model can't read files directly; useful even when it can,
  since it lets you strip/preserve frontmatter, wrap content in
  identifying tags, list bundled resources, enforce permissions, and
  track activation. Constrain the `name` parameter to valid skill names
  (an enum) to prevent hallucinated names; don't register the tool at
  all if no skills exist.

**User-explicit activation** — a slash command or mention syntax
(`/skill-name`, `$skill-name`) the harness intercepts directly, so the
model receives the content without an activation step of its own. An
autocomplete widget helps discoverability.

**What the model receives:** either the **full file** (frontmatter
included — natural for file-read activation, and frontmatter fields
like `compatibility` can be useful context) or **body only**
(frontmatter stripped after being used for discovery — what most
dedicated-tool implementations do). Both are valid.

**Structured wrapping**, for dedicated tools:

```xml
<skill_content name="pdf-processing">
[body content]

Skill directory: /home/user/.agents/skills/pdf-processing
Relative paths in this skill are relative to the skill directory.

<skill_resources>
  <file>scripts/extract.py</file>
  <file>references/pdf-spec-summary.md</file>
</skill_resources>
</skill_content>
```

This lets the model tell skill instructions apart from other content,
lets the harness protect them during compaction, and surfaces bundled
resources without eagerly reading them — the model loads specific files
only when the instructions reference them. Cap the listing for large
skill directories.

**Permission allowlisting:** if your agent gates file access behind
permission prompts, allowlist skill directories — otherwise every
reference to a bundled file triggers a confirmation dialog.

## Step 5: Manage skill context over time

- **Protect from compaction.** If older messages get truncated or
  summarized as context fills, exempt skill content — losing it
  mid-conversation silently degrades behavior with no visible error.
  Flag skill tool outputs as protected, or use the structured tags from
  Step 4 to identify and preserve them.
- **Deduplicate activations.** Track which skills are already in
  context and skip re-injecting one that's requested again.
- **Subagent delegation** (advanced, client-specific): run the skill in
  a separate subagent session instead of injecting into the main
  conversation, returning only a summary — useful when a skill's
  workflow is complex enough to warrant a dedicated, focused session.
