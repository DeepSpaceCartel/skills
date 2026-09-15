# Acceptance testing

Reference: [Terraform Plugin Testing](https://developer.hashicorp.com/terraform/plugin/testing).
Acceptance tests run real `terraform apply`/`refresh`/`destroy` against
your provider — the only way to prove CRUD actually works.

## Setup

```go
var testAccProtoV6ProviderFactories = map[string]func() (tfprotov6.ProviderServer, error){
    "example": providerserver.NewProtocol6WithError(New("test")()),
}

func testAccPreCheck(t *testing.T) {
    if v := os.Getenv("EXAMPLE_ENDPOINT"); v == "" {
        t.Fatal("EXAMPLE_ENDPOINT must be set for acceptance tests")
    }
}
```

## A basic test

```go
func TestAccWidgetResource_basic(t *testing.T) {
    resource.Test(t, resource.TestCase{
        PreCheck:                 func() { testAccPreCheck(t) },
        ProtoV6ProviderFactories: testAccProtoV6ProviderFactories,
        Steps: []resource.TestStep{
            {
                Config: `resource "example_widget" "test" { name = "first" }`,
                Check: resource.ComposeAggregateTestCheckFunc(
                    resource.TestCheckResourceAttr("example_widget.test", "name", "first"),
                    resource.TestCheckResourceAttrSet("example_widget.test", "id"),
                ),
            },
            {
                // update
                Config: `resource "example_widget" "test" { name = "second" }`,
                Check: resource.TestCheckResourceAttr("example_widget.test", "name", "second"),
            },
            {
                ResourceName:      "example_widget.test",
                ImportState:       true,
                ImportStateVerify: true,
            },
        },
    })
}
```

- Each `TestStep` runs a full plan/apply and asserts afterward.
- `ImportState` + `ImportStateVerify` proves the import path round-trips
  to identical state.
- `resource.ComposeAggregateTestCheckFunc` runs all checks even if one
  fails (better diagnostics than `TestCheckFunc`).

## `TF_ACC` gating

`resource.Test` **skips** unless `TF_ACC` is set:

```bash
TF_ACC=1 go test ./... -v -timeout 120m
```

This keeps plain `go test ./...` (unit tests) fast and offline, while CI
runs acceptance tests with real credentials. Never make `go test ./...`
require live infrastructure.

## Useful checks

| Function | Asserts |
| --- | --- |
| `TestCheckResourceAttr(name, key, value)` | attribute equals value |
| `TestCheckResourceAttrSet(name, key)` | attribute is set |
| `TestCheckNoResourceAttr(name, key)` | attribute absent |
| `TestCheckResourceAttrPair(a, ka, b, kb)` | two attributes match |
| `TestMatchResourceAttr(name, key, regex)` | regex match |
| `TestCheckOutput` | output value |

## Plan-only and negatives

```go
{Config: config, PlanOnly: true}                     // expect no error, no apply
{Config: config, ExpectNonEmptyPlan: true}           // a diff is expected
{Config: badConfig, ExpectError: regexp.MustCompile("must be lowercase")}  // validator
```

Use `PlanOnly` to fast-check plan behavior (plan modifiers,
`UseStateForUnknown`, `RequiresReplace`) without provisioning.

## Mocking the API

For providers where live tests are impractical, `terraform-plugin-testing`
can run against a mocked HTTP server: point the provider's endpoint at an
`httptest.Server` in `PreCheck`, and assert the requests the provider
makes. This is still a real Terraform apply — only the remote API is
faked.

Alternatively, unit-test the `internal/client` package directly with
`httptest`, and keep acceptance tests for the wiring.

## CI

```yaml
- run: go test ./...            # unit only (no TF_ACC)
- run: TF_ACC=1 go test ./... -v -timeout 120m
  env:
    EXAMPLE_ENDPOINT: ${{ secrets.EXAMPLE_ENDPOINT }}
    EXAMPLE_TOKEN: ${{ secrets.EXAMPLE_TOKEN }}
```

- Run unit tests on every push; run acceptance tests where credentials
  exist (protected branches, a scheduled job, or a dedicated
  environment).
- Acceptance tests create real resources — be sure `Delete` is tested
  and that tests clean up, including on failure (Terraform destroys at
  the end of `resource.Test`).
- Use a scratch account/namespace per run where possible.

## Sweepers

`resource.Test` cleans up state it created, but resources leaked by a
crash (or created out-of-band) need a **sweeper** — a
`resource.AddTestSweepers("example_widget", ...)` function run via
`go test -sweep=...`. Add one for anything that costs money or hits a
rate limit.
