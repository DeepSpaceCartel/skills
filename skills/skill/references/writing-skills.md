# Writing skills that are well-scoped and effective

Condensed from [agentskills.io/skill-creation/best-practices](https://agentskills.io/skill-creation/best-practices).

## Start from real expertise

Asking an LLM to generate a skill from general training knowledge alone
produces vague, generic procedures ("handle errors appropriately") —
not the specific API patterns, edge cases, and conventions that make a
skill valuable. Feed in domain-specific context instead:

- **Extract from a hands-on task.** Complete a real task in conversation
  with an agent, then pull out the reusable pattern. Pay attention to
  what steps worked, corrections you made along the way ("use library X
  instead of Y," "check for edge case Z"), input/output formats, and
  project-specific context the agent didn't already know.
- **Synthesize from existing artifacts.** Feed an LLM real internal
  docs, runbooks, style guides, API specs, code review comments, issue
  trackers, and version-control history (patches reveal patterns
  through what actually changed). A skill synthesized from your team's
  actual incident reports beats one synthesized from a generic "best
  practices" article.

## Refine with real execution

A first draft usually needs refinement. Run the skill against real
tasks, feed the results — all of them, not just failures — back in, and
ask what triggered false positives, what was missed, what could be cut.
Read execution traces, not just final outputs: wasted steps usually
mean instructions that are too vague, instructions that don't apply but
get followed anyway, or too many options with no clear default. See
[`evaluating.md`](evaluating.md) for a structured version of this loop.

## Spending context wisely

Once active, the full `SKILL.md` body competes for attention with
conversation history, system context, and every other active skill.

- **Add what the agent lacks, omit what it knows.** Don't explain what
  a PDF is or how HTTP works. Ask of every sentence: "Would the agent
  get this wrong without it?" If no, cut it.
- **Design coherent units.** Scope a skill like a function: one
  coherent piece of work that composes with other skills. Too narrow
  and multiple skills must load for one task; too broad and it's hard
  to activate precisely. "Query a database and format results" is
  probably one skill; adding database administration to it is probably
  two.
- **Aim for moderate detail.** Concise, stepwise guidance with a
  working example usually outperforms exhaustive documentation covering
  every edge case — those unproductive paths get triggered even when
  irrelevant. Let the agent's own judgment handle the long tail.
- **Push detail into `references/`** once the skill legitimately
  outgrows ~500 lines / 5000 tokens, and tell the agent exactly *when*
  to load each file ("Read `references/api-errors.md` if the API
  returns a non-200 status code" beats a generic "see references/").

## Calibrating control

Match instruction specificity to how fragile the task is; most skills
mix both.

- **Give freedom** when multiple approaches are valid and the task
  tolerates variation — explaining *why* often works better than a
  rigid directive here, since an agent that understands the purpose
  makes better context-dependent calls.
- **Be prescriptive** when operations are fragile or a specific
  sequence must hold exactly:
  ```markdown
  Run exactly this sequence:
  python scripts/migrate.py --verify --backup
  Do not modify the command or add additional flags.
  ```
- **Provide defaults, not menus.** Pick one tool/approach and mention
  alternatives briefly, rather than listing several as equally valid.
- **Favor procedures over declarations.** Teach *how to approach* a
  class of problems, not the answer to one instance — "read the schema,
  join on the `_id` convention, apply filters as WHERE clauses" reuses
  across queries; "join orders to customers on customer_id, filter
  region='EMEA'" only answers today's question.

## Reusable content patterns

Not every skill needs all of these — use what fits.

- **Gotchas section.** The highest-value content in many skills:
  environment-specific facts that defy reasonable assumptions, not
  generic advice. Keep gotchas in `SKILL.md` itself (not a reference
  file the agent might not know to load) so they're read before the
  mistake happens:
  ```markdown
  ## Gotchas
  - The `users` table uses soft deletes — queries need
    `WHERE deleted_at IS NULL` or results include deactivated accounts.
  - The user ID is `user_id` in the database, `uid` in auth, `accountId`
    in billing. Same value, three names.
  ```
  When you correct an agent's mistake, add the correction here — one of
  the most direct ways to improve a skill.
- **Templates for output format.** A concrete template beats a prose
  description; agents pattern-match well against structure. Short
  templates live inline; longer or situational ones go in `assets/`
  and get referenced.
- **Checklists** for multi-step workflows with dependencies or
  validation gates, so the agent tracks progress and doesn't skip a
  step.
- **Validation loops** — do the work, run a validator (script,
  checklist, self-check), fix issues, repeat until it passes.
- **Plan-validate-execute** for batch or destructive operations: have
  the agent produce an intermediate plan in a structured format,
  validate it against a source of truth, and only then execute. The key
  ingredient is a validator whose errors are specific enough to
  self-correct from (`"Field 'signature_date' not found — available:
  customer_name, order_total, signature_date_signed"`).
- **Bundle reusable scripts.** If execution traces show the agent
  reinventing the same logic each run (a chart builder, a format
  parser), write it once as a tested script in `scripts/` instead. See
  [`scripts.md`](scripts.md).

## Next steps

- [`descriptions.md`](descriptions.md) — test and improve the
  `description` field so the skill triggers on the right prompts.
- [`evaluating.md`](evaluating.md) — set up test cases, grade results,
  and iterate systematically.
