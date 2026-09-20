# Testing

Test strategy and test design: which level to test at, which test double to
use, how to keep tests tied to behavior rather than implementation, and how to
handle flaky tests and untested legacy code. Anchor sources: Fowler's bliki
([Test Pyramid](https://martinfowler.com/bliki/TestPyramid.html),
[Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html),
[UnitTest](https://martinfowler.com/bliki/UnitTest.html)), Beck's
[Test Desiderata](https://testdesiderata.com/), the testing chapters of
[*Software Engineering at Google*](https://abseil.io/resources/swe-book/html/ch12.html),
and Feathers on characterization tests.

## What agents typically get wrong

- **Over-mocking.** Every collaborator is mocked and the test asserts
  `assert_called_once_with(...)`. It is brittle and shows nothing about the real
  system. *Software Engineering at Google* says to prefer real implementations
  and avoid interaction testing.
- **Mirror tests.** The test recomputes the expected value with the
  implementation's own logic, or asserts on internal calls, instead of on
  observable behavior through the public API.
- **Snapshotting current output as the spec** for a *new* feature. That is a
  characterization test, valid for legacy code, not a specification.
- **Coverage chasing.** Tests for getters and trivial code. Coverage shows a
  line ran, not that its behavior was checked.
- **One test per method** instead of one per behavior.
- **Making a flaky test pass** with `sleep`, retries or a longer timeout, rather
  than removing the cause (timing, shared state, concurrency, clocks).
- **Deleting or weakening a failing test**, or "fixing" it to match new buggy
  output.
- **Fakes that drift from the real thing** because nothing tests the fake
  against the real implementation.
- **Changing code and tests together** so the test no longer protects anything.
  A test should change only when the requirement changes.

## Procedure

1. **Define the behavior** as given/when/then, from the spec, docs or bug
   report, never from the implementation.
2. **Pick the lowest level that can fail for this reason.**
   - Pure logic: a fast unit test.
   - Behavior across one boundary (DB, HTTP, filesystem): a narrow integration
     test against a local instance.
   - Agreement between separately deployed services: a contract test.
   - A few critical user journeys: end-to-end.
   - If a high-level test fails and no low-level test does, add the low-level
     test. Push tests as low as they can go.
3. **Choose the double in this order:** real implementation, then fake, then
   stub, then mock.
   - Real if it is fast, deterministic and cheap.
   - Fake for I/O with real semantics (repository, queue, clock), with a
     contract test that also runs against the real implementation.
   - Stub for canned values or hard-to-trigger errors.
   - Mock (interaction check) only when the side effect *is* the requirement and
     no state is observable: send an email, charge a card.
4. **Assert on outcomes:** return values, or state read back through the public
   API. Not call order, not private state.
5. **See it fail first,** or confirm it fails against a deliberately broken
   implementation. Then make it pass.
6. **Ask whether the test is worth writing:** which realistic bug would it
   catch? If flipping `>=` to `>` or dropping a branch fails nothing, strengthen
   it or skip it.
7. **For legacy code with no tests,** write characterization tests before
   changing anything.
8. **If nondeterminism is suspected,** run the tests repeatedly or in random
   order, and fix the root cause. Don't skip the test.

## Techniques

- **Sociable unit tests:** real collaborators, double only the awkward or
  nondeterministic ones. Fowler's own default. Avoid when collaborators are slow
  or cost money.
- **In-memory fake plus contract test** for repositories and clocks. Don't fake
  something whose semantics you can't reproduce (complex SQL): use a containerized
  real one.
- **Characterization test (Feathers):** call the code, assert a placeholder, run,
  read the actual value, paste it in, and name the test for the behavior. Pins
  what code does *now*. "Production becomes its own specification", so
  investigate before "fixing" a quirk, and delete these once proper tests replace
  them.
- **Property-based testing (Hypothesis, QuickCheck).** Good properties: round-trip
  (`decode(encode(x)) == x`), invariants, comparison with a simple reference
  implementation, and stateful model-based tests. Hypothesis shrinks failures to a
  minimal example and remembers them; pin known regressions with `@example`. Avoid
  when the only property available is a copy of the implementation.
- **Mutation testing** measures whether tests detect injected faults. Google runs
  it diff-based and shows results in code review
  ([paper](https://research.google/pubs/state-of-mutation-testing-at-google/)).
  Use selectively on critical logic; whole-repo runs are usually too slow.
- **Contract tests (consumer-driven)** between independently deployed services.
  They replace much end-to-end testing.
- **Flaky tests:** identify, triage, fix the cause. Common causes are timing,
  concurrency, shared state and clocks. Inject a fake clock instead of sleeping;
  quarantine while you fix. Don't blanket-retry.

## Example

```python
from dataclasses import dataclass
from unittest.mock import Mock

@dataclass(frozen=True)
class Order:
    id: int
    sku: str
    qty: int
    total_cents: int

class OrderService:
    def __init__(self, repo):
        self.repo = repo
    def place(self, sku, qty, unit_cents):
        if qty < 1:
            raise ValueError("qty must be >= 1")
        total = qty * unit_cents
        if qty >= 10:
            total = total * 90 // 100      # 10% off for 10 or more
        return self.repo.add(sku, qty, total)

# BAD: coupled to how the service calls the repo, and proves nothing about persistence.
# Passing the same arguments by keyword breaks it, though behavior is identical.
def test_place_bad():
    repo = Mock()
    OrderService(repo).place("A", 10, 200)
    repo.add.assert_called_once_with("A", 10, 1800)

# GOOD: a fake with real semantics, outcomes read back through the public API,
# and cases on both sides of the boundary.
class InMemoryRepo:
    def __init__(self):
        self.rows = {}
    def add(self, sku, qty, total):
        o = Order(len(self.rows) + 1, sku, qty, total)
        self.rows[o.id] = o
        return o
    def get(self, i):
        return self.rows[i]

def test_ten_or_more_items_get_10_percent_off():
    svc = OrderService(InMemoryRepo())
    assert svc.repo.get(svc.place("A", 10, 200).id).total_cents == 1800

def test_nine_items_get_no_discount():
    assert OrderService(InMemoryRepo()).place("A", 9, 200).total_cents == 1800

def test_rejects_zero_quantity():
    import pytest
    with pytest.raises(ValueError):
        OrderService(InMemoryRepo()).place("A", 0, 200)
```

Both boundary cases total 1800, so each is sensitive to a different mutation:
changing `>= 10` to `> 10` fails the first test, and changing it to `>= 9` fails
the second. The bad test breaks on a harmless refactor (calling `add` with keyword
arguments) while the good tests keep passing.

## Gotchas and contested points

- **Pyramid vs trophy.** The pyramid says mostly unit tests; the trophy (Dodds)
  says mostly integration tests because modern tooling makes them fast. Fowler's
  caveat: if high-level tests are fast, reliable and cheap, you don't need
  low-level ones. Choose by the cost and determinism of tests in *your* stack.
- **Classical vs mockist.** Fowler prefers classical (real collaborators). Mockist
  gives outside-in design and sharper failure isolation but couples tests to
  implementation. Default to classical, per Google; use mocks for outbound side
  effects.
- **"Unit" is team-defined,** not necessarily a class.
- **DAMP over DRY in tests.** Some duplication is fine when it makes the test
  clearer.
- **Coverage thresholds** are opinion, not law. Coverage says what ran, not what
  was checked.
- **Retries hide problems.** If a test is marked flaky and retried, the flake
  still needs fixing.

## Review checklist

1. Would this test still pass after a behavior-preserving refactor?
2. Would it fail if I flipped a condition or removed a branch in the code under test?
3. Is the expected value derived from the spec, not from running or copying the code?
4. Is it at the lowest level that can catch the bug?
5. Is every mock justified by an unobservable side effect or a nondeterministic dependency?
6. Does each fake have a contract test against the real implementation?
7. Is it deterministic: no sleeps, no wall-clock, no order dependence?
8. Does the test name state a behavior?

## Related

`debugging` (turn a reproduction into a regression test), `refactoring` (the
safety net comes first), `core-principles` (see program-to-an-interface for
seams, and separation-of-concerns for making logic testable without a database).

## Sources

Fowler: [Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html),
[Test Pyramid](https://martinfowler.com/bliki/TestPyramid.html),
[UnitTest](https://martinfowler.com/bliki/UnitTest.html),
[Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html);
Beck, [Test Desiderata](https://testdesiderata.com/);
*Software Engineering at Google*
[ch. 12](https://abseil.io/resources/swe-book/html/ch12.html) and
[ch. 13](https://abseil.io/resources/swe-book/html/ch13.html);
Petrovic and Ivankovic,
[State of Mutation Testing at Google](https://research.google/pubs/state-of-mutation-testing-at-google/);
Google Testing Blog,
[Where do our flaky tests come from?](https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html);
[Hypothesis docs](https://hypothesis.readthedocs.io/);
Feathers, [Characterization Testing](https://michaelfeathers.silvrback.com/characterization-testing);
Dodds, [Write tests](https://kentcdodds.com/blog/write-tests). Specific flaky-test
statistics are omitted because they could not be checked against the primary source.
