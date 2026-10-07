# Private registries

Source: [Configuring access to private registries for Dependabot](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/configuring-access-to-private-registries-for-dependabot).

Dependabot's updater runs with an **egress allowlist**. It can only
reach hosts declared under the top-level `registries:` key. A registry
configured only in `.npmrc`, `nuget.config`, `settings.xml` etc. is
unreachable, even if it allows anonymous access. Declare it anyway.

```yaml
version: 2
registries:
  npm-internal:
    type: npm-registry
    url: https://npm.example.com
    token: ${{ secrets.NPM_INTERNAL_TOKEN }}
    replaces-base: true          # route ALL lookups here, not just scoped ones
  maven-artifactory:
    type: maven-repository
    url: https://acme.jfrog.io/artifactory/maven
    username: dependabot
    password: ${{ secrets.ARTIFACTORY_PASSWORD }}
updates:
  - package-ecosystem: "npm"
    directory: "/"
    registries: ["npm-internal"]   # or "*"
    schedule:
      interval: "weekly"
```

Defining a registry at the top level isn't enough. Each `updates[]`
entry must also list it under `registries`.

## Registry types

| `type` | Auth | Extras |
| --- | --- | --- |
| `cargo-registry` | `token` | `registry` (name) |
| `composer-repository` | `username` + `password` | |
| `docker-registry` | `username` + `password` | `replaces-base` |
| `git` | `username` + `password` | also used for private Terraform/Swift sources |
| `goproxy-server` | `username` + `password` | |
| `helm-registry` | `username` + `password` | HTTP basic auth only, **not OCI** |
| `hex-organization` | `organization` + `key` | |
| `hex-repository` | `auth-key` | `repo` (required), `public-key-fingerprint` |
| `maven-repository` | `username` + `password` | `replaces-base` |
| `npm-registry` | `username` + `password`, or `token` | `replaces-base`, `scope` |
| `nuget-feed` | `username` + `password`, or `token` | no `replaces-base` |
| `pub-repository` | `token` | |
| `python-index` | `username` + `password`, or `token` | `replaces-base` |
| `rubygems-server` | `username` + `password`, or `token` | `replaces-base` |
| `terraform-registry` | `token` | |

## Secrets

- Reference `${{ secrets.NAME }}`. They resolve from **Dependabot
  secrets** (repo or org level), not Actions secrets.
- Names may contain only letters, digits and `_`. They can't start
  with a digit or `GITHUB_`, and are uppercased.
- Use a read-only credential. The updater only needs to resolve and
  download packages.

## OIDC instead of static secrets

For registries that use `username`/`password`, you can replace those
two fields with provider-specific OIDC fields:

| Provider | Fields |
| --- | --- |
| AWS CodeArtifact | `aws-region`, `account-id`, `role-name`, `domain`, `domain-owner`, optional `audience` |
| Azure DevOps Artifacts | `tenant-id`, `client-id` |
| Cloudsmith | `namespace`, `service-slug`, `audience`, optional `api-host` |
| Google Artifact Registry | `workload-identity-provider`, optional `service-account`, `audience` |
| JFrog Artifactory | `jfrog-oidc-provider-name`, optional `audience`, `identity-mapping-name` |

Prefer OIDC where available. There's no long-lived token to rotate or
leak.

## Gotchas

- **GitHub Packages / GHCR** in the same org need no `registries` entry.
  Grant the repo *Read* under the package's *Manage Actions access*,
  and Dependabot authenticates automatically.
- **Path-prefix matching.** Credentials are matched by URL prefix. If
  a host serves only one registry, omit the path.
- **npm.** Use the raw password, not `.npmrc`'s base64 `_password`.
  Don't add a path to `https://npm.pkg.github.com`. `scope` must start
  with `@`; use one entry per scope. Yarn Berry needs env fallbacks
  (`${NPM_TOKEN-}`) because Dependabot sets no environment variables.
- **Internal networks.** A registry that isn't reachable from the
  internet needs Dependabot on self-hosted runners. Alternatively,
  allowlist Dependabot's IPs from the `actions` key of
  `https://api.github.com/meta`.
- **`insecure-external-code-execution`.** Defining registries turns it
  off for bundler, mix and pip. If you turn it back on, executed
  manifest code can reach only the registries listed in that entry.
  Even so, a malicious package then runs with those credentials.
