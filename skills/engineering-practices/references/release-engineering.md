# Release engineering

Getting a merged change to users safely and often: small batches, trunk-based
development, one build promoted through a pipeline, feature flags, dark launches,
canaries, rollback and roll-forward, and flag cleanup. The mechanics of CI, version
numbers and changelogs are in `github-actions`, `semver` and `keepachangelog`; this is
the decision-making behind them. Anchor sources: DORA's
[research and metrics](https://dora.dev/guides/dora-metrics/),
[trunk-based development](https://trunkbaseddevelopment.com/), Hodgson's
[Feature Toggles](https://martinfowler.com/articles/feature-toggles.html), Google's
[Canarying Releases](https://sre.google/workbook/canarying-releases/) and
[Release Engineering](https://sre.google/sre-book/release-engineering/), and Fowler's
[Blue-Green](https://martinfowler.com/bliki/BlueGreenDeployment.html),
[Canary](https://martinfowler.com/bliki/CanaryRelease.html) and
[Dark Launching](https://martinfowler.com/bliki/DarkLaunching.html) pages.

## What agents typically get wrong

- **One large change.** A whole feature in a single PR or commit. DORA treats work
  that takes more than about a week as too large and warns that AI tooling can
  encourage oversized pull requests.
- **Long-lived branches** and a big-bang merge at the end. Trunk-based development
  wants short-lived branches integrated at least daily.
- **New behavior on by default, with no off switch.** A flag should default to off,
  and flipping it should not need a redeploy.
- **Flags left in forever.** Hodgson: toggles carry inventory cost; add a removal task
  when you create one, give it an expiry, and cap how many exist.
- **A flag tested in only one state.** Test the expected production configuration and
  each release flag both on and off, not every combination.
- **Shipping schema and code as one atomic step.** Separate the schema deploy from the
  application deploy (Fowler); use expand and contract.
- **An irreversible deploy step and no rollback plan.** Hodgson's cautionary tale is
  Knight Capital, where a repurposed flag reactivated old code.
- **Rebuilding the artifact per environment or baking config into it.** DORA's
  deployment-automation guidance: deploy identical packages everywhere, keep config
  separate, use the same process for every environment including production.
- **Judging a canary against "before."** Compare it with a *concurrent* control
  (Google SRE).
- **Applying blue/green or canary ceremony to every change.** Match the ceremony to
  the blast radius.
- **Reusing an old flag name or field.**

## Procedure (shipping a risky change)

1. **Slice into small batches,** hours to a couple of days each, each independently
   mergeable to trunk. Use branch by abstraction for big refactors and Parallel
   Change for interfaces. Merge at least daily.
2. **Ship data changes first, as expand only:** additive and backward compatible, such
   as new nullable columns and dual-writes. Removal comes last, as its own change.
3. **Add a release flag, default off.** Decide at creation time: its owner and type, a
   removal ticket and date, tests for on and off, and a single decision point in the
   code.
4. **Merge and deploy with the flag off.** The code is latent; no user sees anything.
5. **Dark launch** only for invisible back-end behavior where load or latency is the
   risk: run the new path on real traffic and discard or shadow its output. Use a
   canary instead when users must experience the change.
6. **Roll out progressively:** internal users, then a small canary population, then
   larger steps to 100%. Run one canary at a time, compare against a concurrent
   control, pick a few user-facing SLIs, and choose a window that covers peak
   traffic. (The specific ramp percentages are a judgment call, not a standard.)
7. **Declare the rollback trigger up front,** for example error rate above the
   control's by some margin, or a latency SLO breach, and automate the abort where
   you can. Prefer flipping the flag off (or switching the router or artifact) to
   building a new release.
8. **Once it is at 100% and stable, remove the flag and the dead branch,** then run
   the contract phase for any schema or interface change.

**When each step is warranted:** a flag for user-visible, non-trivial or hard-to-revert
behavior (skip it for a trivial internal fix a deploy revert can undo); a dark launch
for a new back-end path with uncertain load; a canary for any change with
production-only risk; blue/green when a fast whole-environment cutover and switch-back
matter more than gradual exposure; expand and contract for anything touching persisted
data.

## Techniques

- **Trunk-based development.** Everyone commits to trunk; branches are short-lived and
  small; CI runs on trunk continuously. DORA's practices: few active branches, merge
  at least daily, no code freezes. Release branches are still allowed, cut just in
  time and cherry-picked from trunk.
- **Toggle categories (Hodgson):**

| Category | Longevity | Notes |
|---|---|---|
| Release | days to weeks | Enables trunk-based development; static |
| Experiment | as long as the experiment | Per-request; needs consistent cohorts |
| Ops | short-lived, or kill switches that stay | Graceful degradation |
| Permission | can be years | Premium tiers, betas; highly dynamic |

  Don't let a release toggle drift into a permission toggle.
- **Blue/green.** Two identical production environments behind a router; rollback is
  switching back. It doesn't solve schema changes or transactions missed during the
  cutover, and it's costly when environments can't be identical.
- **Canary.** A partial, time-limited deployment plus evaluation. Google's example: 5%
  of traffic seeing 20% errors is a 1% overall error rate. Weak for stateful systems.
  Applies to configuration changes too.
- **Rollback vs roll-forward.** Rollback is a fast return to known good, valid only if
  data and contracts stayed compatible. Roll-forward ships a fix. Flag-off is the
  first response, then revert or fix forward.
- **Build once, deploy many:** one artifact promoted through the stages, with config
  external.
- **DORA metrics.** Throughput: lead time for changes, deployment frequency, failed
  deployment recovery time. Stability: change fail rate and deployment rework rate.
  DORA's finding is that speed and stability are not a trade-off.

## Example

A flag with an owner, a default of off and a removal date that fails a test once it
passes, so the flag can't be forgotten:

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class Flag:
    name: str
    kind: str              # release | experiment | ops | permission
    default: bool          # off by default
    owner: str
    remove_by: date
    ticket: str

FLAGS = {"new_pricing_engine": Flag("new_pricing_engine", "release", False,
                                    "team-billing", date(2026, 11, 15), "BILL-482")}

class FeatureDecisions:                    # the single decision point
    def __init__(self, overrides=None):
        self._overrides = overrides or {}
    def enabled(self, name):
        return self._overrides.get(name, FLAGS[name].default)

def price(order, f):
    if f.enabled("new_pricing_engine"):
        return new_engine(order)           # also dual-writes the legacy column
    return old_engine(order)

def test_no_flag_outlives_its_removal_date(today=None):
    today = today or date.today()
    expired = [f.name for f in FLAGS.values() if f.remove_by < today]
    assert not expired, f"remove these flags: {expired}"
```

Run: with the flag left off the old engine is used; with it on, the new one; the
expiry test passes before 2026-11-15 and fails with "remove these flags:
['new_pricing_engine']" after it.

Rollout, as separate deploys:

1. Expand the schema (additive only).
2. Deploy the code with the flag off. The same artifact goes to every environment.
3. Enable for employees, then 1%, 5%, 25%, 100%, comparing the enabled cohort with a
   concurrent control on error rate, p99 latency and a mismatch or refund rate.
4. **Rollback trigger:** any metric worse than the control past the agreed threshold
   means flag off, with no redeploy. Data stays compatible because of the dual-write.
5. After it is stable at 100%: remove the flag and the old engine; later, contract the
   schema. Reverting the code deploy is safe until that last step lands.

The ramp percentages are illustrative.

## Gotchas and contested points

- **Flag debt.** N flags means 2^N states, which can't all be tested. Test production
  config plus each release flag on and off, cap the count, and expire them.
- **Rollback with database changes.** Rolling code back fails if the new code already
  wrote data the old code can't read. Keep the schema compatible with both versions
  and contract only after the change is stable.
- **Canary sample size.** Google gives no fixed number: enough traffic for a
  representative sample, a window that matches your metric interval, no shared
  failure domains, and "the simplest model that meets your objectives". Low-traffic
  services can't detect small regressions quickly.
- **DORA metrics as targets.** DORA cites Goodhart's law: gaming, single-metric focus
  and cross-team comparison all misuse them. Use them per service, as diagnostics.
- **Revert or fix forward** depends on context, and there's no consensus.
- **One canary at a time** is Google's strong advice, not a universal law.

## Review checklist

1. Is the change small enough to merge to trunk in a day or two?
2. Does new behavior default to off, with a flip that needs no redeploy?
3. Does the flag have an owner, a type, a removal date and a removal ticket?
4. Are tests run with the flag both on and off?
5. Are schema and data changes backward compatible, with expand and contract as separate steps?
6. Is one artifact promoted through every environment, with config external?
7. Are canary metrics few, user-facing, compared with a concurrent control, with an explicit abort threshold?
8. Is there a rehearsed rollback that still works after the data has changed?

## Related

`database-migrations` (expand and contract on the data side), `api-evolution`
(compatible interface changes), `reliability` (SLOs that gate a rollout),
`refactoring` (branch by abstraction), and `github-actions` (the pipeline itself).

## Sources

[DORA metrics](https://dora.dev/guides/dora-metrics/),
[working in small batches](https://dora.dev/capabilities/working-in-small-batches/),
[trunk-based development](https://dora.dev/capabilities/trunk-based-development/) and
[deployment automation](https://dora.dev/capabilities/deployment-automation/);
[trunkbaseddevelopment.com](https://trunkbaseddevelopment.com/); Hodgson,
[Feature Toggles](https://martinfowler.com/articles/feature-toggles.html); Google SRE,
[Canarying Releases](https://sre.google/workbook/canarying-releases/) and
[Release Engineering](https://sre.google/sre-book/release-engineering/); Fowler on
[Blue-Green](https://martinfowler.com/bliki/BlueGreenDeployment.html),
[Canary](https://martinfowler.com/bliki/CanaryRelease.html),
[Dark Launching](https://martinfowler.com/bliki/DarkLaunching.html) and
[Parallel Change](https://martinfowler.com/bliki/ParallelChange.html). The books
*Continuous Delivery* and *Accelerate* were not read directly. Specific DORA figures
about AI's effect on delivery, Knight Capital's loss amount and DORA performance
thresholds are omitted because they could not be verified.
