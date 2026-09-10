# Optimizing skill descriptions

Condensed from
[agentskills.io/skill-creation/optimizing-descriptions](https://agentskills.io/skill-creation/optimizing-descriptions).
A skill only helps if it activates — the `description` field is the
entire mechanism agents use to decide whether to load a skill for a
given task. Under-specified and it won't trigger when it should;
over-broad and it triggers when it shouldn't.

## How triggering works

Agents load only `name` + `description` for every skill at startup.
When a task matches a description, the full `SKILL.md` loads. So the
description alone carries the triggering decision. One nuance: agents
typically only reach for a skill when a task needs knowledge beyond
what they can handle alone — a trivial "read this PDF" may not trigger
a PDF skill even with a perfect description, because basic tools
suffice. Specialized knowledge, unfamiliar APIs, and domain-specific
workflows are where a well-written description earns its keep.

## Writing effective descriptions

- **Imperative phrasing.** "Use this skill when..." rather than "This
  skill does..." — the agent is deciding whether to act.
- **User intent, not implementation.** Describe what the user is trying
  to achieve; the agent matches against what was asked, not internal
  mechanics.
- **Err pushy.** Explicitly list contexts where the skill applies,
  including cases that don't name the domain directly ("even if they
  don't explicitly mention 'CSV' or 'analysis'").
- **Concise.** A few sentences to a short paragraph — long enough to
  cover scope, short enough not to bloat context across many skills.
  Hard limit: 1024 characters.

## Designing trigger eval queries

Build ~20 realistic, labeled prompts: 8-10 that should trigger the
skill, 8-10 that shouldn't.

```json
[
  { "query": "I've got a spreadsheet in ~/data/q4_results.xlsx with revenue in col C and expenses in col D — can you add a profit margin column and highlight anything under 10%?", "should_trigger": true },
  { "query": "whats the quickest way to convert this json file to yaml", "should_trigger": false }
]
```

**Should-trigger queries** — vary phrasing (formal/casual/typos),
explicitness (naming the domain vs. describing the need without naming
it), detail (terse vs. context-heavy), and complexity (single-step vs.
buried in a larger workflow). The most useful ones are where the skill
would help but the connection isn't obvious — that's where wording
makes the difference.

**Should-not-trigger queries** — the valuable ones are *near-misses*
that share keywords or concepts but need something different:
`"I need to update the formulas in my Excel budget spreadsheet"` (not
CSV analysis) or `"can you write a python script that reads a csv and
uploads each row to our postgres database"` (ETL, not analysis) — not
`"What's the weather today?"`, which tests nothing.

Use realistic texture throughout: real file paths, personal context
("my manager asked me to..."), specific column/company names, casual
language and typos.

## Testing whether a description triggers

Run each query through the agent with the skill installed; check
whether it invokes the skill (via execution logs, tool-call history, or
verbose output — varies by client). Because model behavior is
nondeterministic, run each query multiple times (3 is a reasonable
start) and compute a **trigger rate** — the fraction of runs that
invoked the skill. A should-trigger query passes above a threshold
(0.5 default); a should-not-trigger query passes below it.

```bash
# Sketch — replace the invocation and detection logic for your client.
check_triggered() {
  local query="$1"
  claude -p "$query" --output-format json 2>/dev/null \
    | jq -e --arg skill "$SKILL_NAME" \
      'any(.messages[].content[]; .type == "tool_use" and .name == "Skill" and .input.skill == $skill)' \
      > /dev/null 2>&1
}
```

## Avoiding overfitting

Split queries into a **train set** (~60%, used to identify failures and
guide edits) and a **validation set** (~40%, used only to check whether
edits generalize). Keep a proportional should/should-not mix in both,
shuffle once, and keep the split fixed across iterations.

## The optimization loop

1. Evaluate the current description on both sets.
2. Identify train-set failures only — don't let validation results
   leak into how you revise.
3. Revise: broaden scope if should-trigger queries fail, add
   specificity about what the skill does *not* do if should-not-trigger
   queries false-trigger. Avoid copying keywords straight from failed
   queries (overfitting) — generalize to the category they represent.
   If stuck after several passes, try a structurally different
   description rather than more tweaking. Stay under 1024 characters.
4. Repeat until train-set queries pass or improvement stalls.
5. Select the iteration with the best *validation* pass rate — not
   necessarily the last one; an earlier draft can generalize better
   than a later, overfit one.

Five iterations is usually enough. If nothing improves, suspect the
queries (too easy/hard/mislabeled) before the description.

## Applying the result

1. Update `description` in the frontmatter.
2. Re-check the 1024-character limit — descriptions tend to grow during
   optimization.
3. Sanity-check with a few manual prompts, or write 5-10 fresh queries
   (never used in optimization) and run them through the eval script
   for an honest read on generalization.

```yaml
# Before
description: Process CSV files.

# After
description: >
  Analyze CSV and tabular data files — compute summary statistics,
  add derived columns, generate charts, and clean messy data. Use this
  skill when the user has a CSV, TSV, or Excel file and wants to
  explore, transform, or visualize the data, even if they don't
  explicitly mention "CSV" or "analysis."
```

## Next step

[`evaluating.md`](evaluating.md) — once triggering is reliable, test
whether the skill's *output* is good.
