# Reliability

Keeping a service inside its objectives under partial failure and overload:
deadlines, retries, idempotency, isolation, load shedding, SLIs, SLOs and alerting,
and learning from incidents. Basic dependency failure modes are already in
`core-principles` (defensive programming); this goes beyond them. Anchor sources:
Google's [SRE book](https://sre.google/sre-book/) and
[workbook](https://sre.google/workbook/alerting-on-slos/), the AWS
[idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
article and [backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
post, the Azure [Retry](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry),
[Circuit Breaker](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
and [Bulkhead](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
patterns, and Allspaw on blameless postmortems.

## What agents typically get wrong

- **Retrying without idempotency.** The server may have processed the request and
  lost only the response. Duplicate charges follow.
- **Generating a new idempotency key per attempt,** which defeats it. The key
  belongs to the logical operation, not the attempt.
- **Retries at every layer.** Four layers with three retries each is 4^3 = 64
  attempts per user action (Google SRE, cascading failures). Retry at one layer;
  lower layers fail fast.
- **Backoff without jitter, or unbounded retries.** Google: always use randomized
  exponential backoff. Brooker's simulations showed no jitter is worst.
- **Retrying errors that can't succeed** (4xx, malformed requests), or retrying
  429/503 blindly instead of honoring `Retry-After`.
- **No timeout, or a fixed timeout per layer with no deadline propagation.** A
  downstream service keeps working on a request whose caller gave up.
- **Alerting on causes** (CPU, queue depth) instead of user-visible symptoms. A page
  should be urgent, actionable, and actively or imminently user-visible.
- **Metrics without an SLO,** and averages that hide the tail: a 100 ms mean can
  hide 1% of requests taking 5 s.
- **A single threshold on the error rate as the alert,** which either pages far too
  often while still meeting the SLO or resets too slowly.
- **Choosing an SLO from current performance, or 100%.**
- **Blaming a person in the postmortem** ("engineer error"). That is the first
  story; the second is the conditions that made it easy.
- **A circuit breaker as a substitute for timeouts.** A long timeout still ties up
  threads before the breaker trips.

## Procedure

**A reliable call path**

1. Classify the operation: naturally idempotent (GET, PUT, DELETE), keyable (POST with
   an idempotency key), or neither. Never auto-retry the last kind.
2. Set a per-attempt timeout from the dependency's latency distribution.
3. Accept an overall deadline and pass the *remaining* budget downstream.
4. Retry at one layer only: capped exponential backoff with full jitter, at most 3
   attempts, and a retry budget.
5. Give each dependency its own pool or semaphore (bulkhead).
6. Add a circuit breaker only if it has a defined fallback.
7. Define the overload response: shed low-criticality work, return a distinct
   "overloaded" status, degrade gracefully.
8. Test with fault injection and load until it breaks.

**An SLO and its alert**

1. Pick user-centric SLIs, defined as good events over valid events.
2. Choose a target agreed by product, engineering and operations. Start loose;
   don't derive it from current performance.
3. Compute the error budget: (1 - SLO) x window. A 99.9% SLO over 30 days is 43.2
   minutes.
4. Write the error-budget policy: what happens when it runs out.
5. Alert on multiwindow, multi-burn-rate (below), and link a runbook from every page.

**A postmortem**

1. Use predefined triggers: user-visible impact over a threshold, any data loss,
   on-call intervention, or manual discovery (which means monitoring failed).
2. Write the timeline, the impact, and contributing factors as "how" and "what",
   not "who".
3. Add prioritized action items, each with an owner. Review and share it widely.

## Techniques

- **Deadline propagation.** Pass the remaining budget down a call chain of depth two
  or more. Without it, a downstream service thinks it has time to spare after its
  caller has given up.
- **Retry budgets** (Google SRE, Handling Overload): at most 3 attempts per request
  and a per-client retry ratio below about 10%. Send the attempt count in request
  metadata so a backend can answer "overloaded, don't retry". Not for calls that
  are never retried.
- **Idempotency keys.** The client generates one key per logical operation. The
  server stores the key atomically with the mutation. The same key with different
  parameters is a validation error; a duplicate still in flight is a conflict;
  replays return an equivalent response. Unnecessary for naturally idempotent
  PUT and DELETE.
- **Circuit breaker** (closed, open, half-open). Protects a shared resource from a
  slow dependency. Skip it for local in-memory resources, where a mesh or load
  balancer already does it, or in queue-driven flows with a dead-letter queue. One
  breaker per independent backend.
- **Bulkheads.** Per-dependency pools and per-tenant partitions, at the cost of
  resource efficiency. Prefer platform limits over hand-rolled ones.
- **Load shedding and adaptive throttling** (Google SRE). Tier requests by
  criticality and shed the lowest first; keep queues short; make degraded modes
  rare and tested.
- **SLIs and SLOs.** Use percentiles, not means. Keep the number of SLOs small and
  the internal SLO stricter than the external SLA.
- **Symptom-based alerting on burn rate.** Google's starting values for a 99.9% SLO
  over 30 days:

| Severity | Long window | Short window | Burn rate | Budget consumed |
|---|---|---|---|---|
| Page | 1 h | 5 min | 14.4 | 2% |
| Page | 6 h | 30 min | 6 | 5% |
| Ticket | 3 d | 6 h | 1 | 10% |

  Each rule fires only when both windows exceed the burn rate, for example
  `error_ratio_1h > 14.4 * 0.001 and error_ratio_5m > 14.4 * 0.001`, where 0.001 is
  the error budget as a fraction. The short window is 1/12 of the long one, so the
  alert also resets quickly. A single burn rate has poor recall: a slow 35x-style
  burn can exhaust a budget without alerting.

## Example

A retry helper with an idempotency key that is stable across attempts, a retry
budget, full jitter and an overall deadline:

```python
import random, time, uuid

class RetryBudget:                     # token bucket: successes earn tokens, a retry costs 1
    def __init__(self, ratio=0.1, max_tokens=10):
        self.ratio, self.max, self.tokens = ratio, max_tokens, max_tokens
    def on_success(self):
        self.tokens = min(self.max, self.tokens + self.ratio)
    def try_spend(self):
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

class Retryable(Exception):            # timeout, connection reset, 429/503 (honor Retry-After)
    pass

def call_with_retries(send, budget, *, max_attempts=3, base=0.1, cap=5.0,
                      deadline_s=10.0, sleep=time.sleep):
    key = str(uuid.uuid4())            # one key per logical operation, reused on every attempt
    deadline = time.monotonic() + deadline_s
    for attempt in range(max_attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("deadline exhausted")
        try:
            result = send(idempotency_key=key, timeout=min(2.0, remaining))
            budget.on_success()
            return result
        except Retryable:
            if attempt == max_attempts - 1 or not budget.try_spend():
                raise
            delay = random.uniform(0, min(cap, base * 2 ** attempt))    # full jitter
            sleep(min(delay, max(0.0, deadline - time.monotonic())))
```

Run against a fake sender that fails twice and then succeeds, the helper succeeded on
the third attempt, sent the same key on all three, and slept for jittered delays
within bounds. With an empty budget it raised after the first failure without
sleeping; a non-retryable error propagated immediately; and a spent deadline raised
`TimeoutError`.

## Gotchas and contested points

- **Retry storms.** Retries are selfish: under persistent overload they amplify load,
  which is why budgets and jitter matter. Bimodal latency is a trap: if 5% of
  requests hit a very long deadline, capacity can collapse.
- **Circuit-breaker tuning is contested.** A long open state raises errors after
  recovery; a short one flaps. Some practitioners prefer a retry budget or token
  bucket to a breaker. Default to a retry budget first.
- **SLO target vs cost.** Each extra nine costs a lot more, and users on an
  unreliable network cannot tell the difference. Overshooting also has a cost:
  users build hard dependencies on the extra reliability.
- **Blameless is not unaccountable.** Accountability comes through owned action
  items, and naming decisions is still allowed.

## Review checklist

1. Is every outbound call bounded by a timeout tied to a propagated deadline?
2. Is retrying done at exactly one layer, with at most 3 attempts, full jitter and a retry budget?
3. Are retries limited to operations that are idempotent or carry a key that is stable across attempts and stored atomically with the mutation?
4. Are non-retryable errors and "overloaded" responses excluded from retry?
5. Does each dependency have its own bulkhead, and does the service have a tested overload path?
6. Is there an SLI defined as good over valid events, an agreed SLO, and an error-budget policy?
7. Do pages fire on multiwindow burn rate (user symptoms), each with a runbook?
8. Does the postmortem describe conditions and decisions, with owned action items, rather than a person as the cause?

## Related

`core-principles` (defensive programming: failure modes of one dependency),
`debugging` (mitigate first during an incident, then find the cause),
`performance` (latency percentiles), `release-engineering` (canaries and rollback),
`database-migrations` (lock timeouts).

## Sources

Google SRE book: [Service Level Objectives](https://sre.google/sre-book/service-level-objectives/),
[Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/),
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/),
[Handling Overload](https://sre.google/sre-book/handling-overload/),
[Postmortem Culture](https://sre.google/sre-book/postmortem-culture/); SRE workbook,
[Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/); AWS,
[Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
and [Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/);
Azure Architecture Center patterns (linked above); the IETF
[Idempotency-Key header draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)
(an expired draft); Allspaw, "Blameless PostMortems and a Just Culture" (read via a
copy). Nygard's *Release It!* and the AWS Builders' Library articles on timeouts and
load shedding could not be fetched, so claims from them are omitted.
