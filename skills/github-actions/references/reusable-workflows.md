# Reusable workflows and composite actions

When three workflows repeat the same ten steps, extract the common
piece. Two mechanisms, different shapes:

| | Reusable workflow | Composite action |
| --- | --- | --- |
| Stored in | `.github/workflows/*.yml` | any dir (`action.yml`) |
| Called with | `uses: org/repo/.github/workflows/x.yml@ref` | `uses: ./path` or `org/repo@ref` |
| Can define jobs | yes | no (steps only) |
| Runner | its own `runs-on` | runs in the caller's job |
| Secrets | passed explicitly or `inherit` | via inputs/env from caller |
| Max nesting | workflows can call workflows | actions can call actions |

## Reusable workflows (`workflow_call`)

```yaml
# .github/workflows/test.yml
on:
  workflow_call:
    inputs:
      node-version:
        type: string
        default: "20"
    secrets:
      registry-token:
        required: false
    outputs:
      result:
        value: ${{ jobs.test.outputs.result }}

jobs:
  test:
    runs-on: ubuntu-latest
    outputs:
      result: ${{ steps.run.outputs.result }}
    steps:
      - uses: actions/checkout@<sha>
      - uses: actions/setup-node@<sha>
        with:
          node-version: ${{ inputs.node-version }}
      - id: run
        run: echo "result=ok" >> "$GITHUB_OUTPUT"
```

Caller:

```yaml
jobs:
  test:
    uses: ./.github/workflows/test.yml
    with:
      node-version: "22"
    secrets: inherit          # or map specific secrets
```

- `permissions` in the caller are **not** inherited by a called
  workflow; the called workflow must set its own (or receive them
  through the caller's `permissions` for the same repo).
- `secrets: inherit` passes all caller secrets — convenient, but prefer
  explicit secret mapping so the callee's needs are visible.
- Pin cross-repo `uses:` to a full SHA, same as actions.

## Composite actions

```yaml
# .github/actions/setup/action.yml
name: Project setup
description: Install tools and dependencies
inputs:
  cache-key:
    description: Extra cache key material
    required: false
    default: ""
runs:
  using: composite
  steps:
    - uses: actions/setup-node@<sha>
      with:
        node-version: "20"
        cache: npm
    - run: npm ci
      shell: bash          # required for composite run steps
```

- Every `run:` in a composite action **must** declare `shell:`.
- Composite actions can't use `secrets` directly and can't set
  `runs-on` — they run in the caller's job.
- Refer to action inputs with `${{ inputs.x }}` (in workflows) and use
  `${{ github.action_path }}` to reference files bundled with the
  action.

## Choosing between them

- Need a whole job (own runner, own `needs`, matrix)? Reusable
  workflow.
- Need a few reusable steps inside an existing job? Composite action.
- Need shared logic across many repos? Central repo with a reusable
  workflow, pinned by SHA, plus repo-level `vars` for config.

## Anti-patterns

- **Copy-paste pipelines**: the same build/test steps in every
  workflow, drifting independently. Extract once.
- **A single mega-workflow** doing lint+test+build+deploy: hard to
  reason about, and a failure anywhere blocks everything. Split by
  concern; chain with `needs:` or `workflow_run`.
- **`secrets: inherit` everywhere**: hides the callee's real
  dependencies and over-shares secrets. Map explicitly where practical.
- **Unpinned cross-repo `uses:`**: a moving tag in another repo is
  remote code execution on your schedule.
