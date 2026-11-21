# Runbooks and safe operations

Writing the page an on-call (or an agent) follows when an alert fires, making the commands in it
safe to run on a production system under stress, and turning a stable runbook into automation.
Anchor sources: the SRE Workbook's [On-Call](https://sre.google/workbook/on-call/) (playbooks) and
[Eliminating Toil](https://sre.google/workbook/eliminating-toil/) (safeguards in automation), and
the SRE book's [Emergency Response](https://sre.google/sre-book/emergency-response/) and
[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/). The rules for
safe operator commands are mostly this skill's synthesis: the sources say to validate inputs, add
timeouts and fall back to a human, but do not list command rules.

## What agents typically get wrong

- **A page with no runbook,** or a runbook link that 404s. The responder reverse-engineers the
  alert at 3 a.m.
- **Heavy diagnostics on the thing that is sick.** A "status" or "stats" call that scans every
  key, walks every partition or takes a global lock, run against a production coordinator or the
  primary database, stalls its write path for minutes. The diagnosis becomes the outage.
- **Admin calls with no timeout.** The command hangs, the operator opens a second terminal and
  runs it again, and now two are hanging.
- **Write commands mixed in with reads,** with nothing marking which ones change state.
- **Empty means everything.** A selector that returns no rows passed to a tool that treats "no
  filter" as "all". The SRE book's machine-wipe incident started that way.
- **Copy-paste placeholders** (`<namespace>`) that run against the default context.
- **Runbooks that drift.** Written once at launch, never updated when the alert fires.
- **Automating a runbook nobody has followed by hand,** or automation with no stop condition.

## Procedure

1. **One runbook per paging alert,** linked from the alert's annotations. Ticket alerts get one
   when the fix is not obvious.
2. **Write it from a real response:** the steps someone actually took, in order, with the commands.
3. **Mark each step** read-only or mutating, with its expected output and how long it should take.
4. **Make reads cheap:** prefer metrics and dashboards; then replicas, followers or read-only
   endpoints; then the primary with a timeout and a row or time limit.
5. **Gate writes:** dry-run first, an explicit confirmation, a named target (never an empty or
   default selector), a cap on how many things one step may touch, and the undo command next to it.
6. **Test the runbook** in a drill or on staging. A runbook nobody has run counts as a draft.
7. **Update it every time the alert fires** and something was missing or wrong (Workbook).
8. **Promote stable, deterministic runbooks to automation** (ladder below), keeping the manual
   version as the fallback.

## Techniques

**Runbook template:**

```
# <AlertName>
Severity: page | ticket      Owner: <team>      Last exercised: <date>
What it means: <the user impact, in one or two sentences>
Dashboard: <link>            Escalate to: <who, after how long>

## Check (read-only)
1. <command>   expect: <output>   takes: <seconds>   source: replica | metrics | primary
## Mitigate (mutating: confirm before running)
2. <command>   effect: <what changes>   undo: <command>   blast radius: <max targets>
## Verify
3. <how to see it worked; the alert clears within N minutes>
## Not this runbook if
- <symptoms that point to a different alert or an incident to declare>
```

**Safe-command rules** (synthesis):

| Rule | Why |
|---|---|
| Read-only by default; mutating steps are labelled and confirmed | A tired operator runs the next line |
| Every admin call has a client-side timeout | A hung call invites a duplicate |
| No full scans, global locks or "stats of everything" on a primary or coordinator | It shares the write path with users |
| Prefer pre-computed metrics over live queries | The answer is already scraped |
| Set statement timeouts on database sessions used for diagnosis | One bad query cannot run for minutes |
| Refuse empty or wildcard target lists | Empty must never mean all |
| Cap the number of targets per step; go in batches | Limits the damage of a wrong selector |
| Pin the context: cluster, namespace, account in the command itself | Defaults change between terminals |
| Write the undo next to the do | Recovery under stress needs no thinking |
| Log what was run, by whom, when | The incident timeline and audit need it |

On Postgres, a diagnostic session sets its own limits before any query: `SET statement_timeout
= '5s'` and `SET lock_timeout = '2s'` (both default to 0, meaning no limit). On Kubernetes, pass
`--context` and `--namespace` explicitly and set `--request-timeout` (its default, 0, never times
out).

**From runbook to automation** (built on the Workbook's toil strategies):

| Stage | What exists | Move on when |
|---|---|---|
| 1. Documented | Steps and commands on a page | It has been followed as written several times |
| 2. Scripted | One script per step, read-only checks built in | The script runs cleanly in drills |
| 3. Human-triggered | A single command or button runs the whole runbook, with a confirmation | It ran in real incidents without edits |
| 4. Automatic | The alert triggers it; a human is told afterwards | Its success rate is tracked and high |

Automation keeps the safeguards of the manual version: input checks, timeouts, caps, a stop when
results look wrong, and a fallback to a human when conditions are unsafe. A page that only ever
needs the same scripted reaction should become stage 4 and stop paging.

## Example

A step wrapper a runbook script can use. Reads run by default; writes need confirmation; every
call has a timeout; an empty target list is refused.

```python
import subprocess, sys

class Refused(Exception):
    pass

def run_step(argv, *, mutates=False, confirmed=False, timeout_s=10, targets=None):
    if targets is not None and len(targets) == 0:
        raise Refused("empty target list: refusing rather than treating it as 'all'")
    if mutates and not confirmed:
        raise Refused(f"mutating step needs --confirm: {' '.join(argv)}")
    try:
        out = subprocess.run(argv, capture_output=True, text=True,
                             timeout=timeout_s, check=True)
    except subprocess.TimeoutExpired:
        raise Refused(f"timed out after {timeout_s}s; do not retry in a loop")
    return out.stdout

py = sys.executable
print(run_step([py, "-c", "print('queue depth 42')"]).strip())
for kw in ({"argv": [py, "-c", "pass"], "mutates": True},
           {"argv": [py, "-c", "import time; time.sleep(5)"], "timeout_s": 1},
           {"argv": [py, "-c", "pass"], "targets": []}):
    try:
        run_step(**kw)
    except Refused as e:
        print("refused:", e)
```

Run: the read printed `queue depth 42`; the unconfirmed write, the 5-second call with a 1-second
timeout and the empty target list were each refused with their message.

## Gotchas and contested points

- **Step-by-step versus general guidance** is contested (Workbook). Step-by-step suits agents and
  new staff; experts want the "what it means" and the dashboard. Keep both in the template.
- **Untested rollback.** The SRE book's test-induced emergency ran long because the rollback had
  never been tried. Exercise the undo, not only the do.
- **Out-of-band access.** If the runbook needs the same system that is down (chat, SSO, the
  cluster's own API), list the out-of-band route.
- **Agents follow runbooks literally.** Ambiguous steps ("check the database") become broad
  queries. Write the exact command, its limit and its source.
- **Read replicas lag.** A diagnostic read from a replica can show old state; say so in the step.

## Review checklist

1. Does every paging alert link a runbook that exists and was exercised recently?
2. Is every step marked read-only or mutating, with expected output and duration?
3. Do diagnostic reads avoid the primary or coordinator's write path, or run there with a
   statement timeout and a limit?
4. Does every admin call have a client-side timeout?
5. Do mutating steps need confirmation, name explicit targets, cap their blast radius and list the
   undo?
6. Is an empty or wildcard target list refused?
7. Are cluster, namespace and account pinned in each command?
8. Is the runbook updated after each use, and is there a plan to script or automate it?
9. Does any automation keep the same safeguards and fall back to a human?

## Related

[monitoring-and-alerting](monitoring-and-alerting.md) (runbook links),
[incident-response](incident-response.md), [toil-and-automation](toil-and-automation.md),
[`core-principles` least privilege](../../core-principles/references/least-privilege.md),
[`data-integrity` corruption-and-bad-writes](../../data-integrity/references/corruption-and-bad-writes.md)
(caps on bulk destruction).

## Sources

SRE Workbook: [On-Call](https://sre.google/workbook/on-call/),
[Eliminating Toil](https://sre.google/workbook/eliminating-toil/); SRE book:
[Emergency Response](https://sre.google/sre-book/emergency-response/),
[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/). The
safe-command rules, the template and the automation ladder are this skill's synthesis. Command
options from the PostgreSQL [client connection defaults](https://www.postgresql.org/docs/current/runtime-config-client.html)
and the [kubectl reference](https://kubernetes.io/docs/reference/kubectl/kubectl/).
