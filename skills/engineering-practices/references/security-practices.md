# Security practices

Three working habits for developers: lightweight threat modeling of a feature,
handling secrets across their lifecycle, and dependency and supply-chain hygiene.
This deliberately leaves out requirement catalogues (see `owasp-asvs`), CI hardening
(`github-actions`), image hardening (`container-images`) and least privilege (in
`core-principles`). Anchor sources: the
[Threat Modeling Manifesto](https://threatmodelingmanifesto.org/), OWASP's
[Threat Modeling](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html)
and [Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
cheat sheets, [SLSA](https://slsa.dev/spec/v1.0/levels), the
[OpenSSF Scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md),
and GitHub's [secret scanning docs](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning).

## What agents typically get wrong

- **Installing packages that don't exist, or aren't the right ones.** A study of 16
  models and 576,000 code samples found about 19.7% of suggested packages did not
  exist (5.2% for commercial models, 21.7% for open-source ones), and 58% of the
  invented names recurred across runs, so an attacker can predict and register them
  ([arXiv 2406.10279](https://arxiv.org/abs/2406.10279)). Rates may have changed
  since. A package that *does* exist is not evidence that it is the right,
  maintained or safe one: typosquats exist too.
- **Hard-coding secrets or committing `.env`,** or putting secrets in environment
  variables. OWASP lists hard-coded secrets, committed `.env` files, secrets in
  environment variables and one secret shared across services as anti-patterns.
- **"Fixing" a leak by deleting the file or rewriting history.** GitHub notes that
  history removal is time-intensive and often unnecessary once the credential is
  revoked. Revoke first.
- **Floating versions:** unpinned dependencies, `latest` tags, and `npm install` in
  CI. `npm ci` fails on a lockfile mismatch and never rewrites the lockfile;
  Scorecard's Pinned-Dependencies check wants versions or hashes.
- **Disabling TLS verification or authentication to get past an error**
  (`verify=False`, `curl -k`, `NODE_TLS_REJECT_UNAUTHORIZED=0`).
- **Logging secrets or whole request objects.**
- **Running `curl | sh` installers or unreviewed install scripts.**
- **Treating threat modeling as a document for a security team** rather than a
  short conversation about the feature being built.

## Procedure

**Threat-model a feature (15 to 30 minutes, four questions)**

1. *What are we working on?* Sketch a data-flow diagram: external entities,
   processes, data stores, flows. Draw trust boundaries wherever privilege or
   ownership changes: browser to API, service to database, your code to third-party
   APIs and packages.
2. *What can go wrong?* Walk STRIDE (Spoofing, Tampering, Repudiation, Information
   disclosure, Denial of service, Elevation of privilege) over each element and each
   flow that crosses a boundary.
3. *What are we going to do about it?* For each threat: mitigate, eliminate,
   transfer or accept. OWASP: mitigations must be actionable, meaning buildable.
4. *Did we do a good job?* Turn each mitigation into a test, a check or a ticket.
   Update the diagram when the design changes.

**Add or update a dependency**

1. Do you need it? Could the standard library or an existing dependency do the job?
2. Verify the name on the registry and against the project's official repository or
   documentation. Never install a name you only recalled.
3. Check for typosquats, publish date, maintainers, recent activity (Scorecard's
   "Maintained"), downloads and license.
4. Pin with a lockfile (commit it), with hashes where supported, and use the frozen
   install command in CI.
5. Review install and post-install scripts; consider disabling them.
6. Consider a cooldown: prefer versions that have been public for a few days, so a
   malicious release has time to be caught. Exempt urgent security fixes explicitly.
   (One analysis found most notable supply-chain attacks were caught within a week;
   that is one author's sample, not a rigorous study, and slow attacks evade it.)
7. Scan for known vulnerabilities, and diff the lockfile: read the transitive
   additions.

**Handle a secret**

1. Prefer not having one: short-lived credentials or federated identity.
2. Otherwise use a secret manager or runtime injection. Never commit it; commit a
   `.env.example` with fake values.
3. Turn on secret scanning and push protection.
4. Scope each secret to one service and rotate it.
5. Never log it; redact at the logging boundary.
6. **After a leak:** revoke or rotate immediately; review access logs for misuse;
   only then clean code, history and logs. Assume it was harvested even if the
   repository was public briefly. Record what happened and add a scanner if one was
   missing.

## Techniques

- **Data-flow diagram plus trust boundaries.** For any feature that adds an input,
  a store, an integration or a privilege change. Skip for pure refactors.
- **STRIDE** is a prompt list for "what can go wrong", not a scoring system.
- **Abuse cases:** write "as an attacker, I..." beside user stories. Useful for
  business-logic flaws STRIDE misses; depends on imagination.
- **Secret scanning plus push protection.** Always on. It catches known patterns
  only, so custom or generic secrets can slip through.
- **Short-lived credentials and rotation.** Dynamic credentials expire on their own.
- **Lockfiles and hash pinning.** Lockfiles for applications and CI; a library's
  lockfile doesn't propagate to its consumers. Pin by hash for release builds.
- **SBOM and provenance.** An SBOM (CycloneDX, SPDX) lists components; it does not
  show they are safe. SLSA v1.0's build track: level 1 provenance exists, level 2
  signed provenance from a hosted platform, level 3 hardened builds.
- **Vulnerability triage:** is it reachable, exploitable in your context, fixable?
  Record the decision (VEX statuses such as "not affected").

## Example

Feature: "upload an avatar image, then call a third-party image API." This is an
illustrative model, not a sourced one. Boundaries: browser to API, API to object
store, API to the third-party API.

| STRIDE | Threat | Mitigation | Verification |
|---|---|---|---|
| Spoofing | Upload as another user | Take the user id from the session, never the request body | Test that a forged id is ignored |
| Tampering | Disguised or polyglot file | Re-encode server-side, allowlist types | Test that a `.php` renamed `.png` is rejected |
| Repudiation | User denies uploading | Audit log with user id and object key, not the image | Log-schema check |
| Info disclosure | Third-party API key in the client bundle or logs | Server-side only, from the secret manager, redacted | Secret scan and a log-redaction test |
| Denial of service | Huge uploads | Size and rate limits | Load test |
| Elevation | Path traversal in the filename | Generate the storage key server-side | Test with `../` names |

Supply-chain line: the new image library is verified on the registry, pinned in the
lockfile, and held for a short cooldown.

## Gotchas and contested points

- **Threat-modeling overhead.** The Manifesto names anti-patterns (the "hero"
  modeler, admiring the problem, over-focus, a perfect representation) and values
  doing it over talking about it, and continuous refinement over a snapshot. Keep it
  small and iterative.
- **Auto-update vs pinning are complementary:** pin, then update through a bot with
  review. Cooldowns delay security patches too, so exempt urgent fixes.
- **Scanner noise.** Tools flag transitive, unreachable or dev-only issues. Triage by
  reachability and record decisions.
- **Environment variables** are OWASP-listed as an anti-pattern yet a common
  injection path. Treat them as acceptable only for short-lived, low-value values,
  and never log the environment.
- **CI-stored secrets** suit low-value secrets only (OWASP).
- **History rewriting** doesn't un-leak a secret and is optional once it is revoked.

## Review checklist

1. Does every new package name exist on the registry, match the project's official repository, and have a real maintainer history?
2. Are versions locked, committed and installed with a frozen install?
3. Is any secret, `.env` or credential file absent from the diff and from logs?
4. Is there a trust-boundary sketch, and was STRIDE applied to each flow that crosses one?
5. Does every accepted threat have an owner, and every mitigation a test or check?
6. Are TLS verification and authentication left on, with no debug bypass?
7. If a secret leaked, was it revoked and rotated before any history cleanup?
8. Are vulnerability findings triaged for reachability, with the decision recorded?

## Related

`owasp-asvs` (requirements), `github-actions` and `container-images` (hardening),
`core-principles` (least privilege), `release-engineering` (dependency updates in
small batches).

## Sources

[Threat Modeling Manifesto](https://threatmodelingmanifesto.org/); OWASP
[Threat Modeling](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html)
and [Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html);
[SLSA levels](https://slsa.dev/spec/v1.0/levels);
[OpenSSF Scorecard](https://github.com/ossf/scorecard/blob/main/docs/checks.md);
[GitHub secret scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning);
[`npm ci`](https://docs.npmjs.com/cli/commands/npm-ci);
[CycloneDX VEX](https://cyclonedx.org/capabilities/vex/);
Spracklen et al., [package hallucinations](https://arxiv.org/abs/2406.10279).
Shostack's four questions and STRIDE are used as commonly taught but were not read
from a primary page. NIST SSDF and CISA Secure by Design are relevant but were only
checked at landing-page level, so no specific practice ids are cited. Specific
package-manager cooldown settings, dependency-confusion details and current
hallucination rates were not verified.
