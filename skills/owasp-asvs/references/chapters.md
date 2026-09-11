# ASVS 5.0.0 Chapters and Sections

Full section breakdown for all 17 chapters, each with a one-line control
objective. Section numbers are the `<section>` in a requirement ID
(`6.2.#` = V6 Authentication → 6.2 Password Security). Section `.1` of a
chapter, when present, is always its **documentation requirements**
section (see the main [`SKILL.md`](../SKILL.md#documentation-requirements-vs-implementation-requirements)).

Source: [github.com/OWASP/ASVS/tree/master/5.0/en](https://github.com/OWASP/ASVS/tree/master/5.0/en)
(one `.md` file per chapter, `0x1#`/`0x2#`-numbered).

## V1 Encoding and Sanitization

Safe processing of untrusted data so it can't be reinterpreted as code
by whatever parses it downstream. Input *validation* (matching business
expectations) lives in V2, not here.

- 1.1 Encoding and Sanitization Architecture — ordering: canonical
  decode once, encode/escape as the last step before the interpreter
- 1.2 Injection Prevention — output encoding by context (HTML/URL/JS),
  parameterized SQL/OS/LDAP/XPath queries, LaTeX, regex, CSV/formula injection
- 1.3 Sanitization — HTML sanitizer libraries, `eval`/dynamic code, SVG,
  templating languages, SSRF allowlisting, JNDI, memcache, format strings, SMTP/IMAP
- 1.4 Memory, String, and Unmanaged Code — buffer/integer overflow, use-after-free
- 1.5 Safe Deserialization — unsafe deserializers, type/allowlist checks on deserialize

## V2 Validation and Business Logic

Input matches functional/business expectations; business-logic flows
can't be reordered, skipped, or automated at abusive scale.

- 2.1 Validation and Business Logic Documentation
- 2.2 Input Validation — allowlists, structural/schema validation, length/range limits
- 2.3 Business Logic Security — step ordering, race conditions, spoofing/tampering
- 2.4 Anti-automation — rate limiting, bot/abuse detection on sensitive flows

## V3 Web Frontend Security

Browser-side attack surface; **does not apply** to machine-to-machine
(no-browser) consumers.

- 3.1 Web Frontend Security Documentation
- 3.2 Unintended Content Interpretation — MIME sniffing, content-type correctness
- 3.3 Cookie Setup — `Secure`/`HttpOnly`/`SameSite` and related attributes
- 3.4 Browser Security Mechanism Headers — CSP, `X-Frame-Options`, etc.
- 3.5 Browser Origin Separation — CORS, cross-origin isolation
- 3.6 External Resource Integrity — Subresource Integrity (SRI) for third-party scripts
- 3.7 Other Browser Security Considerations

## V4 API and Web Service

Applies on top of, not instead of, the authentication/session/input-
validation requirements elsewhere — can't be assessed in isolation.

- 4.1 Generic Web Service Security
- 4.2 HTTP Message Structure Validation
- 4.3 GraphQL — query depth/complexity limits, introspection exposure
- 4.4 WebSocket

## V5 File Handling

Denial of service, unauthorized access, and storage exhaustion via files.

- 5.1 File Handling Documentation
- 5.2 File Upload and Content — type/size validation, content sniffing over extension
- 5.3 File Storage — storage location, permissions, execution prevention
- 5.4 File Download — path traversal, access control on download

## V6 Authentication

Loosely based on [NIST SP 800-63B](https://pages.nist.gov/800-63-3/)
(terminology simplified for clarity, not full compliance). Adaptive/
risk-based authentication step-up lives in V8 (Authorization), since
it's also an authorization concern.

- 6.1 Authentication Documentation — rate limiting/anti-automation config, context-specific word list for passwords, multi-pathway consistency
- 6.2 Password Security — mostly L1; superseded in importance once V6.5 MFA applies
- 6.3 General Authentication Security
- 6.4 Authentication Factor Lifecycle and Recovery — enrollment, recovery, revocation
- 6.5 General Multi-factor Authentication Requirements
- 6.6 Out-of-Band Authentication Mechanisms
- 6.7 Cryptographic Authentication Mechanism
- 6.8 Authentication with an Identity Provider

## V7 Session Management

Correlating a user/device across requests even over stateless protocols.
Cookie-specific rules are in V3; self-contained session tokens (JWT-like)
are in V9 — this chapter is for session mechanics in general, aligned to
[NIST SP 800-63 Digital Identity Guidelines](https://pages.nist.gov/800-63-4/).

- 7.1 Session Management Documentation
- 7.2 Fundamental Session Management Security — uniqueness, unguessability
- 7.3 Session Timeout
- 7.4 Session Termination — logout invalidates server-side state
- 7.5 Defenses Against Session Abuse — concurrent session limits, binding
- 7.6 Federated Re-authentication

## V8 Authorization

Principle of Least Privilege: consumers only reach what their
entitlements permit.

- 8.1 Authorization Documentation — decision factors, environmental context
- 8.2 General Authorization Design
- 8.3 Operation Level Authorization — object- and function-level access control (IDOR-class)
- 8.4 Other Authorization Considerations

## V9 Self-contained Tokens

A token carrying its own claims/data for the receiver to trust (JWT,
SAML assertion) vs. an opaque identifier the receiver looks up locally.
Predates OAuth terminology-wise but applies well beyond OAuth/OIDC.

- 9.1 Token Source and Integrity — signature/MAC validation, algorithm confusion
- 9.2 Token Content — claim validation (audience, expiry, issuer)

## V10 OAuth and OIDC

OAuth = delegated authorization; OIDC = identity layer on top of OAuth.
Roles: client (confidential or public), resource server (RS),
authorization server (AS); OIDC adds relying party (RP) and OpenID
Provider (OP). General web/API requirements from other chapters still
apply — this chapter can't be assessed standalone. Some L1 requirements
relax for confidential (vs. public) clients since strong client
authentication already mitigates the risk.

- 10.1 Generic OAuth and OIDC Security
- 10.2 OAuth Client
- 10.3 OAuth Resource Server
- 10.4 OAuth Authorization Server
- 10.5 OIDC Client
- 10.6 OpenID Provider
- 10.7 Consent Management

## V11 Cryptography

General-purpose cryptographic hygiene; requirements that use crypto to
solve a *different* problem (secrets management → V13, transport
security → V12) live in those chapters instead. See also Appendix C
(Cryptography Standards) for the specific "approved" algorithms/modes.

- 11.1 Cryptographic Inventory and Documentation
- 11.2 Secure Cryptography Implementation — fail securely, no custom crypto
- 11.3 Encryption Algorithms
- 11.4 Hashing and Hash-based Functions — password hashing, HMAC
- 11.5 Random Values — CSPRNG usage
- 11.6 Public Key Cryptography
- 11.7 In-Use Data Cryptography — protecting data while in memory/processing

## V12 Secure Communication

Data-in-transit, both external (client↔backend) and internal
(service↔service). Cryptographic strength detail is again in Appendix C.

- 12.1 General TLS Security Guidance
- 12.2 HTTPS Communication with External Facing Services
- 12.3 General Service to Service Communication Security

## V13 Configuration

Secure-by-default configuration across dev, build, and deployment.

- 13.1 Configuration Documentation
- 13.2 Backend Communication Configuration
- 13.3 Secret Management
- 13.4 Unintended Information Leakage — verbose errors, debug endpoints, stack traces

## V14 Data Protection

What sensitive data needs protecting, how, and specific pitfalls —
particularly on client devices, where usage patterns are least
controllable. Bulk-extraction *detection* is V16's job; *limits* on it
are V2's job — this chapter only covers what/how to protect.

- 14.1 Data Protection Documentation
- 14.2 General Data Protection
- 14.3 Client-side Data Protection — local storage, caching, exposure on-device

## V15 Secure Coding and Architecture

Cross-cutting requirements that don't fit a single functional area —
architecture and dependency hygiene, defensive coding habits, safe
concurrency.

- 15.1 Secure Coding and Architecture Documentation
- 15.2 Security Architecture and Dependencies — dependency vetting/pinning, trust boundaries
- 15.3 Defensive Coding
- 15.4 Safe Concurrency — race conditions, thread safety

## V16 Security Logging and Error Handling

Security logs (auth decisions, access-control decisions, bypass
attempts) are distinct from performance/debug logs — feed detection/
response/SIEM tooling, not general debugging. Must not leak sensitive
personal data, and must themselves be protected as a high-value asset.
See the OWASP Logging Cheat Sheet for implementation detail.

- 16.1 Security Logging Documentation
- 16.2 General Logging
- 16.3 Security Events — what must be logged
- 16.4 Log Protection — tamper resistance, access control on logs
- 16.5 Error Handling — fail securely, no sensitive detail in error responses

## V17 WebRTC

Real-time voice/video/data exchange. Targets product developers, CPaaS
providers, and service providers building or integrating WebRTC
infrastructure — **not** developers who only consume a CPaaS vendor's
SDK/API (the vendor owns that security surface).

- 17.1 TURN Server
- 17.2 Media
- 17.3 Signaling
