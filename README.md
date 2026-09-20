# DeepSpaceCartel Skills

A small pack of project-agnostic [Agent Skills](https://agentskills.io/)
covering public standards and conventions — release & documentation
workflow, API design, data validation, eventing, application security,
development environments, containers & Kubernetes, CI/CD, observability,
infrastructure as code, BDD test specifications, core software design
principles, and Agent Skills authoring itself. None of these are specific
to any one codebase — they document public standards and well-established
practice, and can be dropped into any project.

## Install

```
npx skills add DeepSpaceCartel/skills
```

Or install a single skill, e.g.:

```
npx skills add DeepSpaceCartel/skills/skills/semver
```

## Skills

Grouped the same way as [`skills.sh.json`](skills.sh.json) — keep the
two in sync when adding, moving, or removing a skill.

### Release & Documentation Workflow

Commit messages, changelogs, version numbers, architecture decisions,
and documentation structure.

| Skill | What it covers |
| --- | --- |
| [`adr`](skills/adr/SKILL.md) | Writing and maintaining Architecture Decision Records ([adr.github.io](https://adr.github.io/)) |
| [`conventionalcommits`](skills/conventionalcommits/SKILL.md) | Conventional Commits v1.0.0 message format ([conventionalcommits.org](https://www.conventionalcommits.org/en/v1.0.0/)) |
| [`docs`](skills/docs/SKILL.md) | The Divio documentation system — tutorials, how-to guides, reference, explanation ([docs.divio.com](https://docs.divio.com/documentation-system/)) |
| [`keepachangelog`](skills/keepachangelog/SKILL.md) | Writing a `CHANGELOG.md` in the Keep a Changelog 1.1.0 format ([keepachangelog.com](https://keepachangelog.com/en/1.1.0/)) |
| [`mkdocs`](skills/mkdocs/SKILL.md) | Building a documentation site with MkDocs + Material for MkDocs |
| [`semver`](skills/semver/SKILL.md) | Semantic Versioning 2.0.0 rules ([semver.org](https://semver.org/)) |

### API Design

Structuring REST API requests and responses.

| Skill | What it covers |
| --- | --- |
| [`jsonapi`](skills/jsonapi/SKILL.md) | JSON:API v1.1 response/request format — resources, relationships, CRUD, errors ([jsonapi.org](https://jsonapi.org/)) |
| [`openapi`](skills/openapi/SKILL.md) | OpenAPI 3.1/3.2 descriptions — paths, schemas, components, security schemes, tags, webhooks ([spec.openapis.org](https://spec.openapis.org/oas/v3.2.0.html)) |
| [`rfc9457`](skills/rfc9457/SKILL.md) | Problem Details for HTTP APIs error format ([RFC 9457](https://www.rfc-editor.org/info/rfc9457/)) |

### Data Validation

Describing and validating the shape of JSON data.

| Skill | What it covers |
| --- | --- |
| [`json-schema`](skills/json-schema/SKILL.md) | JSON Schema 2020-12 — validation keywords, `$ref`/`$dynamicRef`, vocabularies, annotations ([json-schema.org](https://json-schema.org/draft/2020-12)) |

### Eventing

Formats and envelopes for event-driven and pub-sub systems.

| Skill | What it covers |
| --- | --- |
| [`cloudevents`](skills/cloudevents/SKILL.md) | CloudEvents v1.0 event format — context attributes, JSON format, protocol bindings, extensions ([cloudevents.io](https://cloudevents.io/)) |

### Application Security

Security requirements and verification standards for building and
assessing applications.

| Skill | What it covers |
| --- | --- |
| [`owasp-asvs`](skills/owasp-asvs/SKILL.md) | OWASP Application Security Verification Standard v5.0.0 — verification levels, requirement chapters, compliance assessment ([owasp.org](https://owasp.github.io/www-project-application-security-verification-standard/)) |

### Agent Tooling

Building and structuring capabilities for AI agents.

| Skill | What it covers |
| --- | --- |
| [`skill`](skills/skill/SKILL.md) | Writing, structuring, and reviewing Agent Skills — the `SKILL.md` format itself ([agentskills.io](https://agentskills.io/)) |

### Development Environments

Configuring reproducible, containerized development environments.

| Skill | What it covers |
| --- | --- |
| [`devcontainer`](skills/devcontainer/SKILL.md) | The Development Container Specification — `devcontainer.json`, Features, Templates, image metadata, distribution ([containers.dev](https://containers.dev/)) |

### Containers & Kubernetes

Building container images and packaging workloads for Kubernetes.

| Skill | What it covers |
| --- | --- |
| [`container-images`](skills/container-images/SKILL.md) | Dockerfiles and image builds — multi-stage, caching, minimal bases, non-root, build secrets, multi-arch ([docs.docker.com](https://docs.docker.com/build/building/best-practices/)) |
| [`helm-charts`](skills/helm-charts/SKILL.md) | Authoring and reviewing Helm charts — values, helpers, hooks, dependencies, testing, upgrade semantics ([helm.sh](https://helm.sh/docs/chart_best_practices/)) |

### CI/CD

Authoring and hardening continuous integration and delivery workflows.

| Skill | What it covers |
| --- | --- |
| [`github-actions`](skills/github-actions/SKILL.md) | GitHub Actions workflows — least-privilege permissions, SHA pinning, fork-PR safety, OIDC, self-hosted runners ([docs.github.com](https://docs.github.com/en/actions)) |

### Observability

Structured logging and telemetry conventions.

| Skill | What it covers |
| --- | --- |
| [`structured-logging`](skills/structured-logging/SKILL.md) | Structured logs and trace correlation per OpenTelemetry — the log data model, semantic conventions, cardinality ([opentelemetry.io](https://opentelemetry.io/docs/specs/otel/logs/data-model/)) |

### Infrastructure as Code

Building and publishing Terraform providers.

| Skill | What it covers |
| --- | --- |
| [`terraform-provider`](skills/terraform-provider/SKILL.md) | Terraform providers with the Plugin Framework — schema, CRUD, import, acceptance tests, docs, Registry release ([developer.hashicorp.com](https://developer.hashicorp.com/terraform/plugin/framework)) |

### Testing & Behavior Specification

Writing behavior-driven test specifications and acceptance criteria.

| Skill | What it covers |
| --- | --- |
| [`gherkin`](skills/gherkin/SKILL.md) | Writing clear, maintainable Gherkin `.feature` files for BDD — declarative style, Background/Scenario Outline usage, tags |

### Software Design Principles

Core, language-agnostic design principles for writing and reviewing code.

| Skill | What it covers |
| --- | --- |
| [`core-principles`](skills/core-principles/SKILL.md) | Sixteen design principles — KISS, DRY, YAGNI, Separation of Concerns, SRP, High Cohesion, Low Coupling, Composition over Inheritance, Information Hiding, Encapsulation, Program to an Interface, Fail Fast, Explicitness, Least Surprise, Least Privilege, Defensive Programming — with a symptom-to-principle lookup, conflict tie-breakers, and a reference per principle |

### Engineering Practices

Time-tested, source-backed workflows for everyday engineering tasks.

| Skill | What it covers |
| --- | --- |
| [`engineering-practices`](skills/engineering-practices/SKILL.md) | Time-tested workflows for everyday engineering tasks — testing, debugging, refactoring, database migrations, reliability, security, API evolution — each with what agents get wrong, a procedure and a checklist, grounded in canonical sources |

## License

MIT, see [LICENSE](LICENSE).
