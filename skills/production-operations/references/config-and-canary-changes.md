# Configuration and canary changes

Designing configuration people can change safely, validating it, rolling it out in stages, and
judging a canary from its numbers. Flags, rollout mechanics and rollback plans are in
[`engineering-practices` release-engineering](../../engineering-practices/references/release-engineering.md);
this reference adds what that one does not cover: configuration as an interface, and how to read a
canary. Anchor sources: the SRE Workbook's
[Configuration Design](https://sre.google/workbook/configuration-design/),
[Configuration Specifics](https://sre.google/workbook/configuration-specifics/) and
[Canarying Releases](https://sre.google/workbook/canarying-releases/), and the SRE book's
[Emergency Response](https://sre.google/sre-book/emergency-response/).

## What agents typically get wrong

- **Treating a config push as safer than a code push.** The Workbook notes most Google incidents
  trace to binary or configuration pushes. The SRE book's change-induced emergency was a global
  config push that had been given a less rigorous canary than usual.
- **A knob for everything.** Each mandatory setting is a question the user must answer and can get
  wrong. Defaults should cover most users.
- **Validation only at runtime.** A typo in a path or a unit mistake is found when the service
  restarts in production, not at review.
- **Unknown keys silently ignored,** so a misspelled setting never takes effect.
- **Config that fetches things while it is evaluated** (a URL, a secret, today's date). The same
  file gives different results tomorrow, and rollback no longer restores the old state.
- **YAML plus a text templating engine** grown into an accidental programming language.
- **Judging a canary against yesterday,** or on a cluster-wide error rate where a 5% canary's
  failures are diluted twenty-fold.
- **A canary window shorter than the metric's aggregation window,** or shorter than one unit of
  work for a batch system.

## Procedure

**Designing a configuration surface**

1. List what users are trying to achieve, then ask the fewest questions that get there. Prefer
   "what" (a target, a tier) over "how" (thread counts, buffer sizes).
2. Turn mandatory settings into optional ones with safe defaults; derive defaults from the
   environment where possible (cores, memory, region).
3. Offer low-level overrides for power users without making everyone see them.
4. Separate the source people edit from the plain data the service reads (JSON, YAML, protobuf).
5. Give every setting an owner, keep it in version control, and log both the edit and the
   resulting change in the system.

**Shipping a config change**

1. Validate at commit: schema, unknown keys rejected, semantic checks (paths exist, units, ranges,
   references resolve), in CI and a pre-commit hook.
2. Evaluate hermetically: same input, same output; no network or clock reads during evaluation.
3. Roll out in stages like code: one canary target, compare with a concurrent control, then widen.
4. Keep the previous version deployable; rollback is re-applying it.
5. Stop automatically, or roll back, if a step loses operator control or breaks the canary
   thresholds.
6. Guard changes that could lock operators out (firewall rules, auth config, admin network
   policy) with a confirm-or-revert timer.

## Techniques

**Config surface design, in short:**

| Choice | Prefer | Avoid |
|---|---|---|
| Questions | few, in the user's terms | every internal parameter |
| Defaults | safe, dynamic where useful | blank mandatory fields |
| Power users | optional overrides | the lowest common denominator for all |
| Format | data compiled from a real config language (Jsonnet, Dhall) or plain data | YAML with string templating; a general-purpose scripting language |
| Evaluation | hermetic, then side effects | queries or writes during evaluation |
| Data model | named objects, grouped by function | arrays of named entries, interpolated strings |

The Workbook names HOCON, Flabbergast, Dhall and Jsonnet as existing configuration languages, and
warns that Python, Ruby or Lua need sandboxing to be hermetic.

**When to evaluate.** Check in generated output (reviewers see the concrete diff, but files get big
and may hold secrets); evaluate at build time and ship the data inside the artifact; or evaluate
at runtime (simplest, but errors surface in production). Pick one per system and say which.

**Guard the evaluator.** Config evaluation can loop or blow up exponentially. If a service
evaluates configs supplied by users, sandbox it with CPU and memory limits.

**Canary analysis.** What [release-engineering](../../engineering-practices/references/release-engineering.md)
already says (concurrent control, few user-facing metrics, one canary at a time) is not repeated.
The additional rules from the Workbook:

| Concern | Rule |
|---|---|
| Breakdown | Metrics must split by canary vs control; aggregate numbers hide a small canary |
| Window | The metric's aggregation window must not be longer than the canary |
| Duration | Long enough to be representative of traffic mix and time of day; at least one full unit of work for batch, rendering or pipeline jobs |
| Batch pipelines | Keep each work unit in one pool (canary or control) through every stage |
| Metric choice | Start with SLIs: failed requests and latency. CPU is usually noisy. Keep to about a dozen at most |
| Attribution | Per-process metrics (CPU spent serving) over whole-machine ones; exclude outlier hosts and shared failure domains |
| Stages | Small first stage with the clearest signals (crashes, errors); richer metrics at larger stages |
| Absolute check | Also check the canary against the SLO itself: shared backends can make canary and control fail together |
| Interpreting a failure | A failing canary is not always the canary's fault; check for cross-talk via shared state |
| Parameters | Use your history of canary failures to set size and duration, not worst-case guesses |

**Error-budget cost.** Exposure scales with the canary share: a change that fails 20% of requests
costs about 1% overall on a 5% canary. A small, quick canary bounds the budget a bad release can
spend.

## Example

A canary verdict with a minimum sample, an absolute SLO check and a relative check that has to
beat noise (two-proportion z score):

```python
import math

def verdict(c_bad, c_total, k_bad, k_total, *, slo_error_ratio,
            max_ratio=1.5, min_requests=500):
    if min(c_total, k_total) < min_requests:
        return "extend", "too few requests to judge"
    c, k = c_bad / c_total, k_bad / k_total
    if c > slo_error_ratio:
        return "abort", f"canary {c:.2%} breaks the SLO"
    p = (c_bad + k_bad) / (c_total + k_total)
    se = math.sqrt(p * (1 - p) * (1 / c_total + 1 / k_total)) or 1e-12
    z = (c - k) / se
    if c > max_ratio * k and z > 3:
        return "abort", f"canary {c:.2%} vs control {k:.2%} (z={z:.1f})"
    return "continue", f"canary {c:.2%} vs control {k:.2%} (z={z:.1f})"

print(verdict(3, 200, 40, 4000, slo_error_ratio=0.01))
print(verdict(30, 5000, 50, 95000, slo_error_ratio=0.01))
print(verdict(60, 5000, 50, 95000, slo_error_ratio=0.01))
print(verdict(9, 5000, 160, 95000, slo_error_ratio=0.01))
```

Run: 200 canary requests gave `extend`; 0.60% against a 0.05% control gave `abort` (z = 13.3)
although it is inside the 1% SLO; 1.20% gave `abort` on the absolute check; 0.18% against 0.17%
gave `continue` (z = 0.2). Feed it counts from the same window, no longer than the canary stage.
The 1.5x ratio and z > 3 are illustrative thresholds, not sourced ones.

## Gotchas and contested points

- **Before/after comparison** confounds the change with time (weekday versus weekend). It can
  still catch a large spike fast, but it is no substitute for a control.
- **Low-traffic services** cannot detect small regressions quickly; lengthen the stage or accept
  only large-effect detection.
- **Rollback needs hermetic config.** If the old version pulls something that changed since, re-
  applying it does not restore the old behaviour.
- **Checked-in generated config** is reviewable but can leak secrets and cause merge conflicts.
- **Synthetic load and traffic teeing** test code paths but not real state; teeing to a system
  with side effects (billing) is dangerous.

## Review checklist

1. Does every mandatory setting need to be mandatory, and does every default suit most users?
2. Is configuration in version control with an owner per setting and a change log?
3. Is it validated at commit for schema, unknown keys and semantic errors?
4. Is evaluation hermetic, with no network, clock or secret reads mixed in?
5. Is a config change rolled out in stages with a canary and a control, like code?
6. Can the previous version be re-applied in one step, and does the rollout stop on loss of
   control?
7. Are canary metrics split by canary and control, over a window no longer than the stage?
8. Does the canary last at least one full work unit for batch systems, and cover representative
   traffic?
9. Is the canary also checked against the SLO, not only against the control?

## Related

[`engineering-practices` release-engineering](../../engineering-practices/references/release-engineering.md)
(flags, rollout, rollback), [`infrastructure-patterns` disruption budgets and safe rollouts](../../infrastructure-patterns/references/disruption-budgets-and-safe-rollouts.md),
[`json-schema`](../../json-schema/SKILL.md) (config schemas), [`helm-charts`](../../helm-charts/SKILL.md)
(values validation), [toil-and-automation](toil-and-automation.md) (configuration toil).

## Sources

SRE Workbook: [Configuration Design](https://sre.google/workbook/configuration-design/),
[Configuration Specifics](https://sre.google/workbook/configuration-specifics/),
[Canarying Releases](https://sre.google/workbook/canarying-releases/); SRE book:
[Emergency Response](https://sre.google/sre-book/emergency-response/). The design table, the
verdict function and its thresholds are this skill's synthesis.
