# Debugging

Systematic diagnosis and repair of a defect: from an observed failure, through the
chain defect, infected state, failure, to a fix that is verified. Anchor sources:
Zeller's free [*The Debugging Book*](https://www.debuggingbook.org/) (the
scientific method of debugging, delta debugging, slicing), Agans's *Debugging: The
9 Indispensable Rules*, Kernighan and Pike's
[*The Practice of Programming*, ch. 5](https://cs.princeton.edu/~bwk/tpop.webpage/debugging.html),
the [`git bisect` docs](https://git-scm.com/docs/git-bisect), and Google's
[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/).

## What agents typically get wrong

- **Patching the symptom.** Swallowing the exception, hard-coding the failing
  input, adding a null check where the wrong value originates upstream. The
  Debugging Book warns against "randomly patching" and hard-coding symptom fixes.
- **Guess-and-check loops.** Trying fix after fix without a hypothesis. A preprint on
  iterative LLM debugging (arXiv 2506.18403) reports steeply diminishing returns
  after a few attempts; treat that as a hint, not a rule. After two or three
  falsified guesses, stop and restate the problem from scratch.
- **Changing several things at once,** so nobody knows which change mattered
  (Agans: change one thing at a time).
- **Fixing without seeing the failure.** Reasoning from the code and claiming the
  bug is "reproduced" without running anything (Agans: quit thinking and look).
- **Declaring victory without a regression test,** or without proving the fix
  matters: put the bug back and confirm the failure returns (Agans: if you didn't
  fix it, it ain't fixed).
- **Making the test pass by editing the test,** the assertion, or the expected value.
- **Trusting the first plausible story.** Google's troubleshooting chapter: horses,
  not zebras, and beware spurious correlations.
- **Skipping the trivial checks:** wrong branch, stale build, wrong environment,
  unsaved config (Agans: check the plug).
- **Refactoring while fixing,** which muddies which change fixed the bug.

## Procedure

Adapted from Zeller's scientific method: observe, hypothesize, predict, experiment,
conclude.

1. **Restate** expected vs actual behavior. Record the exact error, version and
   environment. Check the trivial things first.
2. **Reproduce** with a command you actually ran, and see the failure yourself. If it
   is intermittent, make it fail more often (loops, stress, fixed seeds, added
   delays) rather than theorizing.
3. **Automate and minimize.** Turn the repro into a script or failing test, then
   shrink it.
4. **Find origins.** Work backward from the wrong value through data and control
   dependencies. Look at recent changes first (Kernighan and Pike). Use
   `git bisect` when a known-good state exists.
5. **Hypothesize in writing, one at a time,** each with a prediction that could
   falsify it ("if X, then `v` is null at line N"). Keep a short log of what was
   tried and what is ruled out.
6. **Experiment.** Observe with a log, assertion or debugger. Change nothing else.
   Record negative results too.
7. **Fix the cause,** with one change. Your diagnosis must explain *why* the code
   is wrong, not just where it crashed.
8. **Verify.** The repro now passes. Revert the fix and confirm it fails again, then
   reapply. Run the wider test suite.
9. **Keep the minimized repro as a regression test,** search for the same defect
   pattern elsewhere, and write a one-line root-cause note.

**Stop and ask the user when** no repro is possible with the access you have
(production-only data, hardware, credentials); two or three hypotheses have been
falsified and you are guessing; the fix needs a behavior decision ("what should it
return?"); the fix touches shared, public or security-sensitive code beyond the
report; or the only available fix is a workaround (say so and let them choose).

## Techniques

- **Minimal reproduction.** Always. Don't shrink blindly if the failure is
  nondeterministic: minimizing can change the bug.
- **Delta debugging (ddmin).** Shrinks a failing input, file or diff. It needs a
  deterministic test, and the failure must be the *same* failure. The result is
  1-minimal, not globally minimal.
- **`git bisect`.** Needs a known-good commit and a scriptable test. In `run` mode
  exit 0 means good, 125 means "cannot test this commit, skip", 1 to 127 (except 125)
  means bad, and above 127 aborts. Not useful when history is squashed, when the bug
  comes from an environment change, or when the test is flaky (one wrong verdict
  gives a wrong culprit).
- **Binary search on config, inputs or code:** toggle half the flags or comment out
  half the pipeline.
- **Differential debugging:** compare working vs failing (versions, environments,
  inputs). Fast, but it yields correlations; confirm with an experiment.
- **Assertions** cut the cause-effect chain into shorter pieces and catch the
  infected state earlier.
- **Logs vs debugger.** A debugger is best when you can reproduce locally and need
  to inspect state. Logs and tracing suit concurrency, production and timing
  bugs. Prefer targeted observation tied to a hypothesis over scattering prints.
- **Timing bugs and races** are hard to reproduce, and adding logging can hide
  them by changing timing. Raise the failure rate (stress, race detectors) and
  reason about invariants. Don't "fix" a race with a sleep.

## Example

A regression appeared somewhere between a known-good commit and `HEAD`. The check
script lives *outside* the repository, so old commits can't lack it, and its exit
codes are chosen so that `1` means only "wrong result":

```python
# check.py (kept outside the repo)
import sys
sys.path.insert(0, ".")
try:
    import calc
except Exception:
    sys.exit(125)                     # cannot import at this commit: skip it, don't blame it
sys.exit(0 if calc.add(2, 2) == 4 else 1)
```

```bash
git bisect start HEAD <known-good>
git bisect run python3 /path/outside/repo/check.py
git bisect log            # what was tested; then read the culprit commit
git bisect reset
```

Tested in a throwaway repository with seven commits, one of which does not parse:
with this script `git bisect` skipped the unparseable commit and named the commit
that introduced the bug. With a naive script that imports `calc` unguarded, a
`SyntaxError` also exits 1, so bisect read the unparseable commit as "bad" and
**blamed it instead**. Make "bad" mean only the bug. With pytest, whose exit codes
are 0 (passed), 1 (tests failed) and 2 to 5 (interrupted, internal error, usage
error, nothing collected), map anything other than 0 and 1 to 125.

Bisect names the change, not the cause: read the culprit commit and form a
hypothesis about it.

A simplified input minimizer (greedy chunk removal in the spirit of ddmin; the
Debugging Book has the real algorithm):

```python
def shrink(s, fails):
    assert fails(s)
    n = 2
    while len(s) >= 2:
        chunk = max(1, len(s) // n)
        for i in range(0, len(s), chunk):
            cand = s[:i] + s[i + chunk:]
            if cand and fails(cand):
                s, n = cand, max(n - 1, 2)
                break
        else:
            if chunk == 1:
                break
            n = min(len(s), n * 2)
    return s

# a 26-character failing input shrank to '()' when the failure needed '(' before ')'
```

## Gotchas and contested points

- **Symptom vs root cause under time pressure.** Google's advice is to triage first
  ("make the system work as well as it can"): mitigate (roll back, flag off), then
  find the cause. Mitigation is legitimate if labeled as such and the cause work
  stays open. A symptom patch must be flagged, never presented as the fix.
- **Print vs debugger** is contested. Choose by whether you can reproduce
  interactively.
- **Bisect false verdicts.** A test that doesn't exist yet at old commits, or a
  crash that shares the "bad" exit code, points at the wrong commit. Map exit codes
  explicitly.
- **"It works now" after an unrelated change** usually means the bug is masked, not
  fixed.
- **Correlation traps:** differential debugging shows what differs, not what
  causes.

## Review checklist

1. Did I run a command that showed the original failure before changing code?
2. Is the repro minimized and automated (a script or failing test)?
3. Did I state a hypothesis with a falsifiable prediction before editing?
4. Was each experiment a single change?
5. Does my explanation account for why the wrong value occurred, not just where it crashed?
6. Does the failing test pass with the fix and fail again without it?
7. Did I search for the same pattern elsewhere and run the wider suite?
8. If I mitigated instead of finding the root cause, did I say so?

## Related

`testing` (the regression test), `refactoring` (don't mix it into a fix),
`reliability` (mitigate first during an incident), `performance` (the same
measure-first discipline for slowness).

## Sources

[The Debugging Book](https://www.debuggingbook.org/) (introduction, tracking, and
delta-debugging chapters); [git-bisect](https://git-scm.com/docs/git-bisect);
Google SRE book,
[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/);
Kernighan and Pike,
[ch. 5](https://cs.princeton.edu/~bwk/tpop.webpage/debugging.html);
[MIT 6.031 debugging reading](https://web.mit.edu/6.031/www/sp21/classes/13-debugging/);
Agans's rules via a
[published summary](https://embeddedartistry.com/blog/2017/09/06/debugging-9-indispensable-rules/).
Agans's book and *Code Complete* ch. 23 could not be read directly, so specific rules
from them are cited only through secondary summaries. The bisect and minimizer
examples were run.
