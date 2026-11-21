# Source: google/skills

- Repository: https://github.com/google/skills
- Commit: `613a392` (2026-11-20)
- Licence: Apache License 2.0, copied unchanged as [`LICENSE`](LICENSE). The upstream repo has no NOTICE file.
- Copied unchanged from `skills/cloud/`:
  - `google-cloud-waf-reliability/`
  - `google-cloud-waf-security/`
  - `google-cloud-waf-operational-excellence/`
  - `google-cloud-waf-cost-optimization/`
  - `google-cloud-waf-performance-optimization/`
  - `google-cloud-waf-sustainability/`
- Why: the per-pillar principles of the Google Cloud Well-Architected Framework, used to write the
  provider-neutral crosswalk in `skills/architecture-review/references/provider-crosswalk.md`.

Each `SKILL.md` asks the agent to tag the `gcloud` and Google API commands it runs with an
attribution string (`references/attribution.md`). That applies only when the skill itself is
installed and used against Google Cloud.
