# Evaluating skill output quality

Condensed from
[agentskills.io/skill-creation/evaluating-skills](https://agentskills.io/skill-creation/evaluating-skills).
A skill that seemed to work on one prompt may not work reliably across
varied prompts and edge cases — structured evals answer that and give a
feedback loop for improving the skill systematically.

## Designing test cases

Store test cases in `evals/evals.json` inside the skill directory. Each
has a realistic **prompt**, a human-readable **expected output**, and
optional **input files**:

```json
{
  "skill_name": "csv-analyzer",
  "evals": [
    {
      "id": 1,
      "prompt": "I have a CSV of monthly sales data in data/sales_2025.csv. Can you find the top 3 months by revenue and make a bar chart?",
      "expected_output": "A bar chart image showing the top 3 months by revenue, with labeled axes and values.",
      "files": ["evals/files/sales_2025.csv"]
    }
  ]
}
```

Start with 2-3 cases before expanding. Vary phrasing and formality,
cover at least one boundary condition (malformed input, ambiguous
request), and use realistic context — file paths, column names — rather
than vague prompts like "process this data." Don't define pass/fail
checks yet; add those (assertions) after seeing the first round of
outputs.

## Running evals

Run each test case twice: **with the skill** and **without it** (or
with a previous version), as a baseline. Organize results per iteration:

```
csv-analyzer-workspace/
└── iteration-1/
    ├── eval-top-months-chart/
    │   ├── with_skill/{outputs/, timing.json, grading.json}
    │   └── without_skill/{outputs/, timing.json, grading.json}
    └── benchmark.json
```

Each run needs a clean context — no leftover state from prior runs or
skill development, so the agent follows only what `SKILL.md` says.
Subagents (where supported) give this isolation naturally; otherwise
use a separate session per run. Provide the skill path (or none, for
baseline), the prompt, input files, and an output directory.

When improving an *existing* skill, snapshot it first
(`cp -r <skill-path> <workspace>/skill-snapshot/`) and use the snapshot
as the `old_skill/` baseline instead of `without_skill/`.

**Timing.** Record tokens and duration per run
(`{"total_tokens": 84852, "duration_ms": 23332}`) — a skill that
improves quality but triples token usage is a different trade-off than
one that's both better and cheaper.

## Writing assertions

Add assertions once you've seen real outputs. Good ones are
programmatically or observably checkable and specific: `"The output
file is valid JSON"`, `"The bar chart has labeled axes"`, `"The report
includes at least 3 recommendations"`. Weak ones are too vague
(`"The output is good"`) or too brittle (requiring an exact phrase that
correct-but-differently-worded output would fail). Not everything needs
an assertion — style, visual design, and "does it feel right" are
better caught in [human review](#reviewing-with-a-human).

## Grading

Evaluate each assertion against actual outputs and record **PASS**/
**FAIL** with concrete evidence, not just an opinion:

```json
{
  "text": "Both axes are labeled",
  "passed": false,
  "evidence": "Y-axis is labeled 'Revenue ($)' but X-axis has no label"
}
```

Give outputs + assertions to an LLM for judgment calls; use a
verification script for mechanical checks (valid JSON, row count, file
exists) — scripts are more reliable and reusable across iterations.
Don't give the benefit of the doubt: a "Summary" heading with one vague
sentence still fails an assertion that expects a real summary. While
grading, also flag assertions that are too easy, too hard, or
unverifiable, and fix them for the next iteration.

For comparing two skill versions, try **blind comparison** — show both
outputs to an LLM judge without revealing which is which, scoring
holistic quality (organization, polish, usability) on its own rubric.

## Aggregating and analyzing

Compute per-configuration stats in `benchmark.json` (`pass_rate`,
`time_seconds`, `tokens`, each with mean/stddev, plus the `delta`
between `with_skill` and `without_skill`). A skill that adds 13 seconds
for a 50-point pass-rate gain is probably worth it; one that doubles
tokens for a 2-point gain might not be.

Then look past the aggregate:

- Remove/replace assertions that always pass in both configurations —
  they tell you nothing about the skill's value.
- Investigate assertions that always fail in both — broken assertion,
  too-hard test case, or checking the wrong thing.
- Study assertions that pass with the skill but fail without — that's
  where the skill demonstrably helps; understand why.
- High `stddev` on the same eval across runs means either a flaky eval
  or ambiguous instructions the model interprets inconsistently — add
  examples or tighten the wording.
- Read the execution transcript for any time/token outlier to find the
  bottleneck.

## Reviewing with a human

Assertions only check what you thought to write a check for. Review
actual outputs per test case and record specific, actionable feedback
(`"The chart is missing axis labels and months are alphabetical instead
of chronological"`, not `"looks bad"`). Empty feedback means the case
passed review.

## Iterating on the skill

Combine three signals — failed assertions (specific gaps), human
feedback (broader quality issues), execution transcripts (*why* things
went wrong) — plus the current `SKILL.md`, and ask an LLM to propose
changes. Guide it to:

- **Generalize**, not patch individual test cases.
- **Keep the skill lean** — remove instructions behind wasted work in
  the transcripts; if pass rates plateau despite adding rules, try
  removing some instead.
- **Explain the why** — reasoning-based instructions ("do X because Y
  causes Z") outperform rigid "ALWAYS/NEVER" directives.
- **Bundle repeated work** into `scripts/` when multiple runs
  independently reinvent the same helper logic. See
  [`scripts.md`](scripts.md).

Loop: propose changes → apply → rerun all cases in `iteration-<N+1>/` →
grade and aggregate → human review → repeat. Stop when satisfied,
feedback is consistently empty, or improvement stalls.
