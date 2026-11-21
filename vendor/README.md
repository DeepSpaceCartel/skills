# Vendored provider skills (not part of the pack)

Official skills from cloud providers, copied **unchanged** as source material. The pack's
provider-neutral skills (for example [`architecture-review`](../skills/architecture-review/SKILL.md))
are written from them. They are **not published**: `npx skills add DeepSpaceCartel/skills` discovers
only `skills/*`. Checked 2026-11-20: the default listing shows the 23 pack skills and none of these.
Passing `--full-depth` would also find them; install from the upstream repo instead.

| Directory | Upstream | Licence |
|---|---|---|
| [`google/`](google/SOURCE.md) | [google/skills](https://github.com/google/skills) | Apache-2.0 ([`google/LICENSE`](google/LICENSE)) |

Rules:

- Never edit a vendored file. To refresh, re-copy from upstream and update `SOURCE.md`. A changed
  file would need a prominent change notice (Apache-2.0 §4(b)).
- Text carried from a vendored skill into a pack skill keeps an attribution line naming the
  upstream skill and its licence (Apache-2.0 §4(c)).
- To use these skills yourself, install them from upstream:
  `npx skills add google/skills -g -s google-cloud-waf-reliability` (and so on).
