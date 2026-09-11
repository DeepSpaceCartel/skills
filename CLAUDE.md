# DeepSpaceCartel Skills — working notes

This repo is a pack of project-agnostic [Agent Skills](https://agentskills.io/)
(`skills/<name>/SKILL.md` + optional `skills/<name>/references/*.md`),
published for `npx skills add DeepSpaceCartel/skills[/skills/<name>]`.

## Adding or renaming a skill — three places, not one

Adding a new skill touches **three** files. It's easy to do only the
first and silently leave the pack's own index stale:

1. **`skills/<name>/SKILL.md`** (+ `references/` if the body would
   exceed ~500 lines / ~5000 tokens). `name` in frontmatter must equal
   the directory name; `description` must state what it covers *and*
   when to use it (that's the entire activation signal — see
   `skills/skill/SKILL.md` for the full spec).
2. **`skills.sh.json`** — add the skill to an existing `groupings[]`
   entry, or add a new grouping if none fits. Validate it's still
   valid JSON after editing.
3. **`README.md`** — add a row to the skills table, alphabetically by
   skill name, following the existing `| [`name`](skills/name/SKILL.md) | one-line summary (spec link) |` format.

Renaming or removing a skill means updating all three the same way,
plus checking for cross-skill relative links (e.g.
`keepachangelog/SKILL.md` links to `../semver/SKILL.md`).

## Style precedent to match

Look at `semver`, `keepachangelog`, and `mkdocs` before writing a new
skill — they're the clearest examples of the pack's actual voice:
terse rule-first prose, a worked example before/after, and (for
larger skills) a "Where to look" table pointing into `references/`.
`skills/skill/SKILL.md` is the meta-skill describing the format itself
— read it when in doubt about frontmatter or directory conventions.

## Committing

This repo is the user's own; changes here are otherwise treated like
any other git repo — don't commit unless asked.
