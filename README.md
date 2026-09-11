# DeepSpaceCartel Skills

A small pack of project-agnostic [Agent Skills](https://agentskills.io/) for
the release and documentation workflow: writing commits, changelogs,
version numbers, architecture decision records, and documentation sites.
None of these are specific to any one codebase — they document public
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

| Skill | What it covers |
| --- | --- |
| [`adr`](skills/adr/SKILL.md) | Writing and maintaining Architecture Decision Records ([adr.github.io](https://adr.github.io/)) |
| [`cloudevents`](skills/cloudevents/SKILL.md) | CloudEvents v1.0 event format — context attributes, JSON format, protocol bindings, extensions ([cloudevents.io](https://cloudevents.io/)) |
| [`conventionalcommits`](skills/conventionalcommits/SKILL.md) | Conventional Commits v1.0.0 message format ([conventionalcommits.org](https://www.conventionalcommits.org/en/v1.0.0/)) |
| [`docs`](skills/docs/SKILL.md) | The Divio documentation system — tutorials, how-to guides, reference, explanation ([docs.divio.com](https://docs.divio.com/documentation-system/)) |
| [`jsonapi`](skills/jsonapi/SKILL.md) | JSON:API v1.1 response/request format — resources, relationships, CRUD, errors ([jsonapi.org](https://jsonapi.org/)) |
| [`keepachangelog`](skills/keepachangelog/SKILL.md) | Writing a `CHANGELOG.md` in the Keep a Changelog 1.1.0 format ([keepachangelog.com](https://keepachangelog.com/en/1.1.0/)) |
| [`mkdocs`](skills/mkdocs/SKILL.md) | Building a documentation site with MkDocs + Material for MkDocs |
| [`owasp-asvs`](skills/owasp-asvs/SKILL.md) | OWASP Application Security Verification Standard v5.0.0 — verification levels, requirement chapters, compliance assessment ([owasp.org](https://owasp.github.io/www-project-application-security-verification-standard/)) |
| [`rfc9457`](skills/rfc9457/SKILL.md) | Problem Details for HTTP APIs error format ([RFC 9457](https://www.rfc-editor.org/info/rfc9457/)) |
| [`semver`](skills/semver/SKILL.md) | Semantic Versioning 2.0.0 rules ([semver.org](https://semver.org/)) |
| [`skill`](skills/skill/SKILL.md) | Writing, structuring, and reviewing Agent Skills — the `SKILL.md` format itself ([agentskills.io](https://agentskills.io/)) |

## License

MIT, see [LICENSE](LICENSE).
