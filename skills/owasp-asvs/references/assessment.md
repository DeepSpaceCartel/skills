# Assessment, Verification, and Certification

Source: [0x04-Assessment_and_Certification.md](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x04-Assessment_and_Certification.md).

## OWASP does not certify anyone

OWASP is a vendor-neutral nonprofit and does not certify vendors,
verifiers, or software. A trust mark, badge, or "OWASP ASVS-certified"
claim is never an official OWASP endorsement, however legitimate the
underlying assessment might be. Organizations may sell ASVS-based
assurance services, but claiming *OWASP* certification specifically is
false regardless of the work quality behind it.

## What a real verification report includes

Traditional penetration-test reports work "by exception" — only failures
are listed. An ASVS assessment report is different in kind: it should
state the **scope** (which level was targeted, which chapters/
requirements were in scope and which excluded, and why), a summary of
**every** requirement checked (pass, fail, and not-applicable), and
guidance for resolving each failure. A requirement marked not
applicable (e.g. session-management requirements against a stateless
API) still needs to appear in the report with its justification — it
should never simply be omitted.

The report should be written from the "what was included" perspective,
not "what wasn't excluded" — the reader needs to be able to reconstruct
exactly how much of the application was actually assessed.

## Verification mechanisms

No single method covers ASVS end to end. Verifiers commonly need:

- Valid-credential penetration testing (full application coverage,
  not black-box)
- Source code / static review
- Configuration review
- Access to documentation and to the people who made the design/
  implementation decisions being checked — especially for L2/L3, where
  many requirements are only checkable this way

Certifying organizations should disclose their testing method and keep
it repeatable, and back findings with real evidence (screenshots,
scripts, work papers, logs) — an off-the-shelf tool run with no further
verification does not constitute having tested a requirement.

## Automated tooling: useful, not sufficient

DAST/SAST tools, correctly tuned into a build pipeline, can catch some
classes of issue reliably (output encoding, some straightforward
injection patterns) — for those, a finding should simply never make it
to production. But poorly tuned tools generate enough noise to bury
real findings, and no off-the-shelf tool can evaluate business logic,
access control, or documentation requirements.

The recommended middle path for anything beyond the mechanical
requirements: write application-specific automated checks (unit/
integration-style tests targeting specific abuse cases) reusing
existing test infrastructure. E.g. a login-controller test suite should
also fuzz the username field for enumeration/default-account/injection
issues and the password field for null-byte injection, length abuse,
and parameter removal — not just functional login/logout paths.

**"Testable using automation" does not mean "solved by running an
off-the-shelf tool."**

## Penetration testing: hybrid, not black-box

Black-box testing (no docs, no source access) is explicitly discouraged
as an assurance activity, even though ASVS 4.0's L1 was historically
tuned to be reachable that way. Testing without access to
documentation/source misses threats and missing controls that a
source- or doc-informed ("hybrid") tester would catch in far less time,
and it's actively insufficient for verifying most L2/L3 requirements.
Prefer giving testers full access to developers and documentation over
a traditional black-box engagement.
