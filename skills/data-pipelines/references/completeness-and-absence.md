# Completeness and absence

Most pipelines that track items over time (listings, catalogue entries, accounts, files) infer
deletion from absence: an item known yesterday and not seen today is closed. That inference is
only as good as the read. This reference covers proving a read was complete before acting on
what it didn't see, page-walk stop rules, stated totals, empty results, and telling our own
failures from the source's. It is mostly this skill's synthesis; the nearest published support
is the [SRE Workbook](https://sre.google/workbook/data-processing/) (downstream work should wait
for complete input, since late data does less harm than wrong data; per-stage success can hide
end-to-end loss), and the safe-delete guards in
[corruption-and-bad-writes](../../data-integrity/references/corruption-and-bad-writes.md).

## What agents typically get wrong

- **Stopping at the first short page.** `if len(page) < page_size: break` treats a source quirk
  (a filtered row, a per-page cap, an item deleted between requests) as the end of the list.
  Every item after that page is then "gone".
- **Treating an empty result as "zero items".** A timeout swallowed into `[]`, a login wall, a
  changed URL, a bot check or an error page parsed as no rows all look empty. Only the source
  saying it has zero items means zero.
- **Ignoring a total the source states.** If the response says 812 and the walk saw 640, the
  walk is incomplete, whatever the stop rule said.
- **Recording our failure as the source's.** Our connection pool starves, our deadline is too
  short, our DNS resolver fails, our IP is blocked: every target fails at once, and each is
  marked dead or empty. The source is fine.
- **One flag for "run ok".** A run can be complete for 900 sources and partial for 100. The
  proof is per source, per run.
- **Closing in the same step as reading.** Diff and close run inside the walk, so a crash or
  exception mid-walk leaves half the items closed.
- **No brake on mass closure.** A run that would close 80% of a source's items is far more
  likely a broken read than a real event. Nothing holds it for a look.

## Procedure

1. **Write down each source's completeness evidence** before writing the client: a stated total,
   a final-page marker, a cursor that ends, an explicit "no results" notice, or none. Sources
   with none can add items but never close them on absence alone.
2. **Walk to a positive end.** Continue past short pages until an empty page, an end marker or
   an exhausted cursor. Cap the number of pages, and treat hitting the cap as incomplete.
3. **Check the walk against the evidence.** Distinct IDs seen against the stated total. A page
   larger than the page size, a total that changes mid-walk, or a repeated cursor all fail the
   walk.
4. **Treat zero only as stated.** An empty result closes items only when the source positively
   says it has none, recognised by a marker seen on a real empty source, not a guessed phrase.
5. **Class every failure** (table below). Our-side and unknown failures change nothing about the
   source: no closes, no "dead" status, no backoff of the source.
6. **Read, then diff, then write**, as separate steps. The diff runs only on a walk marked
   complete, and the writes are idempotent (see [idempotent-stages](idempotent-stages.md)).
7. **Hold mass closures.** If a run would close more than a set share of a source's known items,
   write nothing and send it for review. Tune the share per source from history.
8. **Fail loudly.** An incomplete walk fails that source's run and shows on the dashboard. It
   doesn't retry silently forever, and it doesn't count as fresh.

## Techniques

**Stop rules, strongest first**

| Evidence | Proves complete when | Watch for |
|---|---|---|
| Stated total | Distinct IDs seen equals it | Approximate or capped totals ("1000+"), totals before filtering |
| End marker (`has_more: false`, no next link) | It appears, after the last item | Markers that are always false on error pages |
| Cursor | Server returns no next cursor | A cursor that repeats or resets: fail |
| Empty page after the last item | The page after the data is empty | Only safe if empty pages never appear mid-list |
| "No results" notice | A recognised notice is present | Matching a sentence you never saw on a real empty source |
| None of these | Never; add-only | Closing on absence here is guessing |

**Error classes**

| Class | Examples | Effect on the source's record |
|---|---|---|
| Source says gone | 404/410 on the item or the whole source, a stated total of 0 | May close, after the walk proves it |
| Source unhappy | 429, 503, `Retry-After`, a bot-check page | Back off that source; close nothing |
| Source changed | Unknown schema or markup, a missing required field | Fail and alert for a parser fix; close nothing |
| Ours | Pool exhausted, our deadline, DNS failure, TLS setup, disk full, OOM | Close nothing; alert on our own health |
| Unknown | Anything unclassified | Treated as ours |

**Canary sources.** Keep a few sources that are known to be up and stable, read them on every
worker and every run, and alert when they fail. If canaries fail with the rest, the fault is
ours. A burst of failures across unrelated sources at the same moment points the same way.

**Separate deadlines.** Distinguish "the source took too long" from "our run ran out of time".
Time out waiting for a free connection apart from waiting for the server, and log which one
fired. A request that never left the pool is our failure.

**A pinned snapshot, where offered.** Some APIs let a walk pin a snapshot or sort by a stable key.
Prefer them to offset paging on a list that changes while you walk it.

## Example

A page-walk guard that continues past short pages to an empty page, checks a stated total, and
refuses to close items when the walk wasn't proven complete or would close too many.

```python
from dataclasses import dataclass, field

class IncompleteRead(Exception):
    """The walk did not prove it saw every item; absence means nothing."""

@dataclass
class Walk:
    ids: set = field(default_factory=set)
    stated_total: int | None = None

def walk(fetch_page, page_size, max_pages=10_000):
    """fetch_page(n) -> (items, stated_total or None). Stops only on an empty page."""
    w = Walk()
    for n in range(max_pages):
        items, total = fetch_page(n)
        if total is not None:
            if w.stated_total not in (None, total):
                raise IncompleteRead(f"total changed mid-walk: {w.stated_total} -> {total}")
            w.stated_total = total
        if not items:                          # the only stop signal: an empty page
            break
        if len(items) > page_size:
            raise IncompleteRead(f"page {n} has {len(items)} > page_size {page_size}")
        w.ids.update(i["id"] for i in items)   # a short page is NOT the end
    else:
        raise IncompleteRead(f"no empty page within {max_pages} pages")
    if w.stated_total is not None and len(w.ids) != w.stated_total:
        raise IncompleteRead(f"saw {len(w.ids)} distinct ids, source states {w.stated_total}")
    return w

def diff(known: set, w: Walk, *, max_close_ratio=0.2):
    """Return (new, closed). Refuse a close the walk can't justify."""
    new, closed = w.ids - known, known - w.ids
    if known and not w.ids and w.stated_total != 0:
        raise IncompleteRead("empty result without the source stating zero items")
    if known and w.ids and len(closed) / len(known) > max_close_ratio:
        raise IncompleteRead(f"would close {len(closed)}/{len(known)}; hold for review")
    return new, closed
```

The checks fake a source with 250 items in pages of 50, where page 1 returns 49 (a quirk), so
the pages hold 50, 49, 50, 50, 50 and 1 items:

```python
def raises(fn):
    try: fn()
    except IncompleteRead: return True
    return False

ids = [f"item-{k}" for k in range(250)]
pages = [ids[0:50], ids[50:99], ids[99:149], ids[149:199], ids[199:249], ids[249:]]
quirky = lambda n: ([{"id": x} for x in pages[n]] if n < len(pages) else [], 250)
w = walk(quirky, page_size=50)
assert len(w.ids) == 250 and diff(set(ids), w)[1] == set()        # nothing closed
naive = set(ids[0:50]) | set(ids[50:99])     # `break` when len(page) < 50 stops after page 1
assert len(set(ids) - naive) == 151                                 # would close 151 live items
short = lambda n: ([{"id": x} for x in ids[n*50:(n+1)*50]] if n < 4 else [], 250)
assert raises(lambda: walk(short, page_size=50))                    # states 250, serves 200
assert raises(lambda: diff(set(ids), walk(lambda n: ([], None), 50)))
assert len(diff(set(ids), walk(lambda n: ([], 0), 50))[1]) == 250  # stated zero closes all
no_total = lambda n: ([{"id": x} for x in ids[n*50:(n+1)*50]] if n < 2 else [], None)
assert raises(lambda: diff(set(ids), walk(no_total, 50)))           # 150 of 250 closing: held
```

All six checks passed on Python 3.13: the guard walked all 250 items past the short page
and closed none; the naive loop would have closed 151 still-listed items; a stated total of 250
against 200 served raised; an empty result without a stated zero raised instead of closing
everything; a stated zero closed all 250; and a walk that saw 100 of 250 known items (no total)
was held for review.

## Gotchas and contested points

- **Totals move during a walk.** On a busy source, a total that changes mid-walk can be real. Retry
  the walk once from the start before failing; don't accept the mismatch.
- **Dedupe before counting.** Offset paging over a changing list can repeat or skip items. Count
  distinct IDs, and expect a skip to show up as a count shortfall.
- **The mass-close threshold is a judgement.** Too low and real clear-outs wait for a person; too
  high and a broken read gets through. Set it per source from its history of closures.
- **Add-only sources drift.** Without completeness evidence, closed items stay open forever. Mark
  them unverified after a period, or verify each item directly, rather than guessing.
- **Retrying hides the class.** A retry loop that ends in a generic "failed" loses whether the
  failure was ours. Keep the class of the last attempt.

## Review checklist

1. For each source, is the completeness evidence written down, and do sources without any
   never close on absence?
2. Does the walk continue past short pages to a positive end (empty page, end marker, exhausted
   cursor), with a page cap that counts as incomplete?
3. Is the count of distinct IDs checked against any stated total, and does a mismatch fail the
   walk?
4. Does an empty result close items only when the source explicitly states zero, recognised from
   a real empty source?
5. Is every failure classed as source-gone, source-unhappy, source-changed, ours or unknown,
   with only source-gone allowed to close?
6. Are canary sources read on every worker, and does their failure mark the run as our fault?
7. Are pool-wait, connect and read timeouts distinguished, and are pool-wait timeouts ours?
8. Is the diff a separate step that runs only on a walk marked complete?
9. Is a run that would close more than a set share of a source's items held for review?
10. Does an incomplete walk fail visibly and leave the source not fresh?

## Related

[pipeline-slos](pipeline-slos.md) (completeness and freshness SLIs),
[idempotent-stages](idempotent-stages.md) (read, diff and write as separate stages),
[failure-isolation](failure-isolation.md) (backoff per source),
[corruption-and-bad-writes](../../data-integrity/references/corruption-and-bad-writes.md)
(caps on bulk deletes, soft delete),
[reliability](../../engineering-practices/references/reliability.md) (timeouts and retries).

## Sources

Google SRE Workbook, [Data Processing Pipelines](https://sre.google/workbook/data-processing/)
(delayed data: wait rather than run on incomplete input; end-to-end versus per-stage checks).
The stop-rule and error-class tables, canary sources, and the mass-close hold are this skill's
synthesis; no fetched source states them.
