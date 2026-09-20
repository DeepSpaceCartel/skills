# Performance

Making software faster or cheaper by measurement, not guesswork: define the metric,
profile, benchmark, tell latency from throughput, and apply the usual fixes. Anchor
sources: Brendan Gregg on the
[USE method](https://www.brendangregg.com/usemethod.html),
[methodology](https://www.brendangregg.com/methodology.html) and
[flame graphs](https://www.brendangregg.com/flamegraphs.html); the Google SRE book's
[Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
(percentiles, the four golden signals); Knuth's 1974 "Structured Programming with go
to Statements"; and Gil Tene on
[coordinated omission](https://groups.google.com/g/mechanical-sympathy/c/icNZJejUHfE/m/BfDekfBEs_sJ).

## What agents typically get wrong

- **Optimizing from reading the code instead of from a profile.** Knuth: intuitive
  guesses about where the time goes fail. Gregg lists the "random change" and
  "streetlight" anti-methods.
- **Quoting "premature optimization is the root of all evil" to refuse any
  performance work,** and dropping the other half of the passage: don't pass up
  opportunities in the critical 3%, but only after that code has been identified by
  measurement. (Read from secondary sources; the original PDF could not be fetched.)
- **Reporting mean latency.** A 100 ms average can hide 1% of requests taking 5 s.
  Use percentiles.
- **Timing a single run,** or timing on a noisy or cold machine.
- **Microbenchmarks the compiler or JIT optimizes away,** or that use unrepresentative
  inputs.
- **Load tests that back off when the server stalls (coordinated omission),** which
  understates tail latency.
- **Trusting a profiler as a timer.** Python's docs note that profilers aren't for
  accurate benchmarking.
- **Chasing constant factors** (comprehension vs loop) while an O(n^2) scan or an N+1
  query sits in the hot path.
- **Adding a cache with no invalidation rule, size bound or measured hit rate.**
- **Declaring "faster" from one before/after pair,** with no variance or
  significance check.
- **Ignoring Amdahl's law:** speeding up a part that is 5% of the runtime can't
  give more than about 1.05x overall.

## Procedure

1. **State the problem:** which operation, which metric (p50/p99 latency,
   throughput, memory, cost), what target, and whether it regressed. Ask what
   changed recently.
2. **Build a representative, repeatable workload** with production-like data size,
   shape and concurrency.
3. **Take a baseline** with several runs on an idle machine, and report a
   distribution, not one number.
4. **Profile the real workload.** Use a sampling profiler where possible, and pick the
   view that matches the symptom: CPU, wall-clock or off-CPU, memory, lock
   contention. If the cause isn't obvious, check utilization, saturation and errors
   for each resource (USE).
5. **Form a hypothesis from the top of the profile** and estimate the ceiling with
   Amdahl: a hot spot that is a fraction p of the runtime can give at most
   1/(1-p).
6. **Change one thing.**
7. **Re-measure the same workload** and compare with variance in mind. Keep the change
   only if the difference is real and worth the complexity; otherwise revert.
8. **Re-profile,** because the bottleneck moves. Stop when the target is met.
9. **Guard it:** a regression benchmark or an alert, and a correctness test so a
   faster wrong answer fails.

## Techniques

- **Sampling profiler** (py-spy, pprof, JFR, perf, browser DevTools). Low overhead,
  can attach to a live process. For I/O-bound code the CPU view misleads, so use
  wall-clock or off-CPU.
- **Deterministic profiler** (`cProfile`). Exact call counts; sort by `tottime` to find
  hot loops and by `cumulative` for hot subtrees. Not for timing: it inflates the
  cost of many small calls.
- **Flame graph.** Width is the share of samples, the x-axis is alphabetical rather than
  time, the y-axis is stack depth.
- **USE method.** For each resource (CPU, memory, disk, network, and software ones
  such as locks and pools): utilization, saturation, errors. Averages hide bursts.
- **Golden signals:** latency, traffic, errors, saturation. Track the latency of failed
  requests separately: a fast error flatters the numbers.
- **Percentiles.** Report p50, p95, p99 and max. Don't average percentiles across
  instances; merge the underlying histograms.
- **Benchmark hygiene:** warm up, consume results so nothing is optimized away, use a
  harness (`timeit`, `go test -bench`, JMH), run on an idle machine, repeat, and
  compare distributions.
- **Open-loop load generation** with a fixed arrival rate, so a stalled server doesn't
  slow the test down and hide the tail.
- **Algorithm and data-structure fixes** (list to set or dict, indexing, sorting) are
  usually the biggest win. Not when `n` is tiny (see the example).
- **N+1 and batching:** in ORMs, `select_related` (a join) and `prefetch_related` (a
  second query); bulk inserts; request batching; pagination.
- **Caching** on read-heavy, expensive, repeatable paths that tolerate staleness, with
  an invalidation rule, a TTL, a size bound and a measured hit rate.
- **Concurrency** helps for I/O waits or independent work. It is capped by the serial
  fraction, locks and pool sizes, and in CPython the GIL limits CPU-bound threads.

## Example

Measured on this machine with Python 3.12 (your numbers will differ; the method is
the point). A function that removes items already in a `known` list:

```python
def dedupe_known(items, known):           # known is a list: each `in` is a linear scan
    return [x for x in items if x not in known]
```

1. **Baseline** (5000 items, 5000 known, `timeit.repeat`, 5 runs): minimum 382 ms,
   median 533 ms.
2. **Profile** (`python -m cProfile -s tottime slow.py`): 0.524 of 0.546 s inside
   `dedupe_known`.
3. **Hypothesis:** `x not in known` is a linear scan over a list, so the whole loop is
   O(n*m).
4. **One change:** build a set once.

```python
def dedupe_known(items, known):
    known = set(known)
    return [x for x in items if x not in known]
```

5. **Re-measure with the same workload:** median 0.75 ms, about 650x faster, and the
   results are identical (asserted on the workload).
6. **Check the edge:** for tiny inputs the change is *slower* (n=1 about 0.84x, n=3
   about 0.7x); it breaks even between 3 and 10 items and is 16x faster at 100. Keep
   the correctness assertion in the test suite and add a benchmark sized like the
   real workload.

Note the baseline's minimum and median differ by 40% on identical runs: report
variance, not one number.

## Gotchas and contested points

- **Knuth's quote is misread.** It concerns small efficiencies in code you haven't
  measured, not architecture: choices such as the data model, N+1 queries or chatty
  APIs are cheap early and expensive to retrofit.
- **Performance vs readability.** Optimize only the measured hot path, isolate it,
  comment why, and keep the simple version as a test oracle.
- **`min` vs median.** Python's `timeit` docs favor the minimum to estimate the
  noise-free cost of a snippet; benchstat-style comparison uses many runs, the
  median and a significance test. Use `min` for deterministic CPU-bound
  microbenchmarks and distributions for anything with real variance (I/O, GC, JIT).
- **Benchmarks are not production.** Data size, cache warmth, contention and noisy
  neighbours differ. Validate with production metrics or a canary.
- **Latency vs throughput.** Improving one can hurt the other: batching raises
  throughput and adds latency.
- **A profiler changes what it measures.** Deterministic profilers distort relative
  costs; prefer sampling for the real picture.

## Review checklist

1. Is there a stated metric, target and baseline from a repeatable, representative workload?
2. Was the bottleneck found with a profiler, not by reading code?
3. Is the hot spot big enough, by Amdahl, to matter?
4. Was a single change measured with repeated runs and a variance check?
5. Are latencies reported as percentiles, with a load generator that avoids coordinated omission?
6. Does any new cache have an invalidation rule, a bound and a measured hit rate?
7. Is the result verified correct against the old output and guarded by a benchmark or alert?
8. Is the added complexity justified by the measured gain?

## Related

`reliability` (overload and tail latency under load), `debugging` (the same
reproduce-then-measure discipline), `database-migrations` (index and query changes),
`core-principles` (kiss and yagni: don't add complexity without a measured need).

## Sources

Gregg: [USE method](https://www.brendangregg.com/usemethod.html),
[methodology](https://www.brendangregg.com/methodology.html),
[flame graphs](https://www.brendangregg.com/flamegraphs.html); Google SRE book,
[Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/);
Python docs on [profilers](https://docs.python.org/3/library/profile.html) and
[timeit](https://docs.python.org/3/library/timeit.html);
[py-spy](https://github.com/benfred/py-spy);
[Go pprof](https://go.dev/blog/pprof);
[benchstat](https://pkg.go.dev/golang.org/x/perf/cmd/benchstat);
[Amdahl's law](https://en.wikipedia.org/wiki/Amdahl%27s_law); Knuth's passage as
discussed in [Revisiting Knuth's premature-optimization paper](https://probablydance.com/2025/06/19/revisiting-knuths-premature-optimization-paper/);
Django [`select_related`](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related).
Gregg's *Systems Performance*, Bentley's *Programming Pearls*, and Tene's talk itself
were not read directly. The example's numbers were measured for this document.
