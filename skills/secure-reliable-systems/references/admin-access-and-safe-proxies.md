# Administrative access and safe proxies

How people, agents and automation change production: through a few narrow admin operations
behind a safe proxy, with multi-party approval for the risky ones, an audit record for every
call, and a break-glass path that works when the proxy or the identity system is down. How to
derive a minimal grant is in [`core-principles` least-privilege](../../core-principles/references/least-privilege.md);
how to write the commands a runbook runs is in
[`production-operations` runbooks-and-safe-operations](../../production-operations/references/runbooks-and-safe-operations.md).
This page is about the access path itself. Anchor sources:
[BSRS ch. 3, Safe Proxies](https://google.github.io/building-secure-and-reliable-systems/raw/ch03.html),
[ch. 5, Design for Least Privilege](https://google.github.io/building-secure-and-reliable-systems/raw/ch05.html),
[ch. 1](https://google.github.io/building-secure-and-reliable-systems/raw/ch01.html) and
[ch. 14](https://google.github.io/building-secure-and-reliable-systems/raw/ch14.html) (break-glass
for deploy policy).

## What agents typically get wrong

- **Shell access as the admin interface.** SSH or `kubectl exec` gives the whole POSIX API. It
  can't be narrowed to one operation, and session recording is easy to sidestep (BSRS ch. 5).
- **A broad cluster credential handed to an agent or a script,** with no record of what it ran.
  When something breaks, nobody can say whether the agent did it.
- **No break-glass path,** or one nobody has used since it was set up. The proxy, the SSO or the
  secret store is down, and the only way in depends on it.
- **Break-glass that is quiet.** No alarm, no review, so it slides into the daily route and the
  reviews turn into rubber stamps (BSRS ch. 5).
- **Self-approval.** A "two-person" rule where the requester can approve their own request, or
  where an approver sees only "approve?" with no context.
- **A proxy that targets can be reached around.** Policy lives in the proxy, but the backend
  still accepts direct connections, so the proxy is advice.
- **The proxy as a new single point of failure** with no second instance and no fallback.
- **Free-text justifications** ("fixing stuff") that no program can check.

## Procedure

1. **List the admin operations people actually run.** Read shell history, runbooks and incident
   timelines. Group them into a small set of named operations: restart a workload, drain a node,
   rotate a key, read a config, change a flag. Each takes typed arguments and a bounded target
   list.
2. **Classify each operation by risk** (BSRS ch. 5): read or write, which data class it touches,
   how many targets one call can reach. Controls scale with the class, not one standard for all.
3. **Put a safe proxy in front.** Clients call the proxy; the proxy checks policy, logs, waits
   for approval if needed, then forwards the call under the caller's identity, so the proxy holds
   little privilege of its own. Targets accept admin calls only from the proxy (BSRS ch. 3). For a tool you can't change, wrap the
   tool: the proxy runs the CLI with a checked argument list.
4. **Require a machine-checkable reason** on every write: an incident or ticket id that the proxy
   can verify is open. Alert on generic or reused reasons (BSRS ch. 5).
5. **Add multi-party authorization** for destructive or wide operations. The approver is not the
   requester, sees the exact command, targets and reason, and can refuse. For high-value actions,
   consider approval on a separate hardened device, so a compromised workstation can't approve
   its own request (BSRS ch. 5's "three-factor" idea).
6. **Prefer temporary grants** over standing ones: access that expires after hours, tied to the
   reason that unlocked it.
7. **Design break-glass** (below) before the proxy goes live, not after the first lockout.
8. **Run more than one proxy instance,** keep its dependencies inside its own SLO, and document
   who to call when it's down (BSRS ch. 3).
9. **Review the logs.** The owning team reviews its routine events; a separate reviewer looks
   for misuse. A frequent break-glass reason means a missing admin operation: add it.

## Techniques

**Break-glass that will work on the day:**

| Property | What it means in practice |
|---|---|
| Low-dependency | Doesn't need the proxy, the SSO, the main secret store or the cluster's own API. Offline credentials in a sealed store with a separate access path (BSRS ch. 9, 15) |
| Restricted | Only the team holding the service's SLO; for the most sensitive systems, only from a controlled location or device (BSRS ch. 5) |
| Loud | Every use fires a high-confidence alert to people other than the user, and is logged with who, what, when and why |
| Reviewed | Each use is reviewed afterwards; the root cause of needing it is fixed |
| Tested | Exercised on a schedule, end to end, including fetching the sealed credential |
| Rare | Measured. A rising count is a design bug, not a habit to accept |

Recovery copies of break-glass credentials, and where they live, are covered in
[`data-integrity` disaster-recovery](../../data-integrity/references/disaster-recovery.md).

**Agents and automation** (synthesis, built on BSRS ch. 3 and 5):

- **One identity per agent or job,** never a person's credential or a shared admin kubeconfig.
  The audit log must be able to tell "agent 7 drained the node" from "Alice did".
- **Agents call the proxy's named operations,** not a shell. The narrow API is what makes the
  log readable and the grant small.
- **Agents never hold standing write access.** They request a temporary grant tied to a ticket,
  or a human approves the write.
- **Agents can't approve each other** or their own requests; an approval needs a human or a
  separate policy service.
- **Keep long-lived credentials out of the agent's sandbox.** The agent holds only a short-lived
  identity that lets it ask the proxy, so a prompt-injected agent can ask but not act past policy.

**What a safe proxy buys and costs** (BSRS ch. 3):

| Buys | Costs |
|---|---|
| One place for policy, audit, approval and rate limits | Another service to run and keep available |
| Controls for closed-source tools | Policy mistakes block real work; use templates and safe defaults |
| Gradual rollouts of wide changes (rate limit per call) | Friction that pushes engineers to look for a way around |
| Actions run under the caller's identity, so the proxy itself holds little privilege | An attractive target; harden and monitor it like production |

Latency is a cost too, but ch. 3 doesn't discuss it.

**Deploy-policy break-glass** (BSRS ch. 14). The admission check that rejects unsigned or
unprovenanced artifacts needs its own bypass for an outage, with the same properties: alarmed,
audited, rare. Log every bypass so the deployment can be re-checked afterwards.

## Example

A minimal policy decision for a safe proxy: named operations only, a role check, a verifiable
reason, a target cap, approval by someone other than the caller, an audit record for every
decision, and an alarm on break-glass.

```python
import json, time
from dataclasses import dataclass, field

@dataclass
class Rule:
    action: str; roles: set; approvals: int = 0; max_targets: int = 1

POLICY = {r.action: r for r in [
    Rule("restart_pod", {"oncall", "deploy-bot"}, approvals=0, max_targets=5),
    Rule("drain_node", {"oncall"}, approvals=1, max_targets=1),
]}

@dataclass
class Request:
    caller: str; roles: set; action: str; targets: list; justification: str
    approvers: set = field(default_factory=set); breakglass: bool = False

def decide(req, audit, alarm):
    rule = POLICY.get(req.action)
    if req.breakglass:
        alarm(f"BREAKGLASS by {req.caller}: {req.action} {req.targets} ({req.justification})")
        verdict = "allow-breakglass"
    elif rule is None:
        verdict = "deny: unknown action"                 # no generic "shell" operation
    elif not (req.roles & rule.roles):
        verdict = "deny: role"
    elif not req.justification.startswith(("INC-", "TKT-")):
        verdict = "deny: needs a ticket or incident id"  # then check it is open
    elif not req.targets or len(req.targets) > rule.max_targets:
        verdict = f"deny: targets must be 1..{rule.max_targets}"   # empty never means all
    elif len(req.approvers - {req.caller}) < rule.approvals:
        verdict = f"pending: needs {rule.approvals} approver(s) other than the caller"
    else:
        verdict = "allow"
    audit(json.dumps({"ts": time.time(), "caller": req.caller, "action": req.action,
                      "targets": req.targets, "why": req.justification,
                      "approvers": sorted(req.approvers), "verdict": verdict}))
    return verdict
```

Run against seven requests: an agent restarting one pod was allowed; the same agent draining a
node was denied on role; Alice approving her own drain stayed pending, and with Bob's approval it
was allowed; an empty target list and a `shell` action were denied; a break-glass drain was
allowed and raised one alarm. All seven decisions, denials included, produced an audit record.

## Gotchas and contested points

- **Fail open or closed when the proxy is down?** Security favours closed, reliability open
  (BSRS ch. 8). Keep the proxy closed and make break-glass the open path, so the exception is
  loud and narrow instead of silent and total.
- **Narrow APIs need upkeep.** Each new incident type may need a new operation. If adding one
  takes weeks, people use break-glass instead.
- **Approvals fatigue.** Approvers who see dozens a day approve without reading. Keep
  multi-party approval for the operations that need it and show the diff, not a yes/no.
- **Broad read access has value.** BSRS ch. 5 notes that wide visibility (source code, for
  example) helps people learn; spend strictness on sensitive assets and writes.
- **Interactive debugging still happens.** When a shell is unavoidable, grant it temporarily
  through the proxy, to one host, with the session logged and the grant expiring.

## Review checklist

1. Is every routine production change one of a small set of named operations, rather than a shell
   or exec session?
2. Do the targets accept admin calls only from the proxy (or the deploy choke point)?
3. Does every write carry a reason the system can verify, and are generic reasons alerted on?
4. Do destructive or wide operations need approval by someone other than the requester, who sees
   the exact command and targets?
5. Does each agent and automation job have its own identity, act through the proxy, and leave an
   audit record of every call, denials included?
6. Does break-glass work with the proxy, SSO and main secret store all down, and was it tested
   end to end in the last quarter?
7. Does every break-glass use fire an alarm to someone other than the user and get reviewed?
8. Is the break-glass count tracked, and does each recurring reason become a new narrow
   operation?
9. Does the proxy run as more than one instance, with a documented fallback?

## Related

[credential-lifecycle-and-rotation](credential-lifecycle-and-rotation.md) (the credentials these
paths use), [compromise-recovery-and-forensics](compromise-recovery-and-forensics.md) (audit logs
an actor can't erase), [`core-principles` least-privilege](../../core-principles/references/least-privilege.md),
[`production-operations` runbooks-and-safe-operations](../../production-operations/references/runbooks-and-safe-operations.md),
[`owasp-asvs`](../../owasp-asvs/SKILL.md) (application authorization).

## Sources

BSRS [ch. 1](https://google.github.io/building-secure-and-reliable-systems/raw/ch01.html),
[ch. 3](https://google.github.io/building-secure-and-reliable-systems/raw/ch03.html),
[ch. 5](https://google.github.io/building-secure-and-reliable-systems/raw/ch05.html),
[ch. 8](https://google.github.io/building-secure-and-reliable-systems/raw/ch08.html),
[ch. 9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
[ch. 14](https://google.github.io/building-secure-and-reliable-systems/raw/ch14.html),
[ch. 15](https://google.github.io/building-secure-and-reliable-systems/raw/ch15.html), paraphrased.
The agent rules, the break-glass property table and the policy code are this skill's synthesis.
