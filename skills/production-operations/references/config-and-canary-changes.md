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

1. Fix the contract first: the service reads only generated plain data (JSON, YAML, protobuf)
   with a schema you own, and whatever people edit (a config language, a UI) compiles to it.
2. Make the common case a short file. State outcomes (a target, a tier), not mechanisms (thread
   counts, buffer sizes); anything else gets a safe default, and values that depend on the host
   (cores, memory, region) are computed there rather than asked for.
3. Put the low-level controls behind explicit overrides that experts can reach and nobody else
   has to read.
4. Make every change traceable: one owner per setting, history in version control, and a record
   of both the commit and the moment it took effect in the running system.

**Shipping a config change**

1. Validate at commit: schema, unknown keys rejected, semantic checks (paths exist, units, ranges,
   references resolve), in CI and a pre-commit hook.
2. Evaluate hermetically: same input, same output; no network or clock reads during evaluation.
3. Keep the last good version one command away: rollback means re-applying it, which only
   works if step 2 holds.
4. Push it like a binary: one canary target judged against a concurrent control, then wider
   steps, and the pipeline halts or reverts by itself when a step trips the canary thresholds or
   cuts operators off.
5. Apply anything that could lock operators out (firewall rules, auth config, admin network
   policy) under a timer that reverts unless someone confirms from the new state.

## Techniques

**Config surface design, in short:**

| Layer | Good sign | Warning sign |
|---|---|---|
| What people edit | a few outcome-level inputs, mostly optional; expert overrides out of the default view | a form listing every internal parameter, or one low-level shape forced on everyone |
| How it is written | plain data, or a purpose-built config language (Jsonnet, Dhall) compiled to it | text templates over YAML; a general-purpose scripting language |
| What the service reads | maps keyed by name, related settings in one subtree, produced by a pure evaluation with side effects only afterwards | lists of entries carrying a `name` field; strings with interpolation; lookups or writes while evaluating |

The Workbook names HOCON, Flabbergast, Dhall and Jsonnet as existing configuration languages, and
warns that Python, Ruby or Lua need sandboxing to be hermetic.

**When to evaluate.** Pick one moment per system and write it down. Inside the running service is
the least machinery, but mistakes show up only in production. In the build, with the data shipped
in the artifact, source and output can't drift apart. Committing the output beside its source
shows reviewers the literal diff, at the price of bulky files and a place for secrets to leak.

**Guard the evaluator.** Config evaluation can loop or blow up exponentially. If a service
evaluates configs supplied by users, sandbox it with CPU and memory limits.

**Canary analysis.** What [release-engineering](../../engineering-practices/references/release-engineering.md)
already says (concurrent control, few user-facing metrics, one canary at a time) is not repeated.
The additional rules from the Workbook:

| Question | Answer |
|---|---|
| What to compare | Every canary metric split into canary and control, since a fleet-wide figure buries a 5% slice. Numbers owned by the serving process (its own CPU time, its own errors) beat host totals; odd hosts are left out. The two groups share backends and can sink together, so the canary also has to clear the SLO on its own |
| Which signals | The user-facing SLIs (errors, latency) first; resource numbers like CPU are noisy. A short list people trust, on the order of ten, beats a long one they learn to ignore. Blunt signals (crashes, failed requests) suit a tiny first stage; subtler ones can join as the stages grow |
| How long | Never shorter than the window a metric is aggregated over, and long enough to see a typical request mix and peak hours. Batch, rendering or pipeline work needs at least one whole work unit, and a unit stays with the same group (canary or control) at every step. Calibrate size and length against your own canary record |
| What a red result means | Stop and investigate, but don't convict the new version yet: shared state can carry a fault from one group to the other |

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
- **Committed generated output** shows a change's real effect, but expect merge conflicts when many
  sources feed one file, and scan it for secrets.
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
