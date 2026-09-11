# DeepSpaceCartel Skills

A small pack of project-agnostic [Agent Skills](https://agentskills.io/)
covering public standards and conventions — release & documentation
workflow, API design, data validation, eventing, application security,
BDD test specifications, and Agent Skills authoring itself. None of
these are specific to any one codebase — they document public
standards and can be dropped into any project.

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

### Testing & Behavior Specification

Writing behavior-driven test specifications and acceptance criteria.

| Skill | What it covers |
| --- | --- |
| [`gherkin`](skills/gherkin/SKILL.md) | Writing clear, maintainable Gherkin `.feature` files for BDD — declarative style, Background/Scenario Outline usage, tags |

## License

MIT, see [LICENSE](LICENSE).
