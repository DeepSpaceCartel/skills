# Framework schema

Reference: <https://developer.hashicorp.com/terraform/plugin/framework>.
This covers the provider, resource, and data-source schema objects and
their attributes.

## Provider

```go
func (p *exampleProvider) Schema(ctx context.Context, req provider.SchemaRequest, resp *provider.SchemaResponse) {
    resp.Schema = schema.Schema{
        MarkdownDescription: "Manages Example resources.",
        Attributes: map[string]schema.Attribute{
            "endpoint": schema.StringAttribute{
                Optional:            true,
                MarkdownDescription: "API endpoint. Defaults to EXAMPLE_ENDPOINT.",
            },
            "token": schema.StringAttribute{
                Optional:            true,
                Sensitive:           true,
                MarkdownDescription: "API token. Defaults to EXAMPLE_TOKEN.",
            },
        },
    }
}

func (p *exampleProvider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
    var cfg exampleProviderModel
    resp.Diagnostics.Append(req.Config.Get(ctx, &cfg)...)
    if resp.Diagnostics.HasError() { return }

    client, err := client.New(cfg.Endpoint.ValueString(), cfg.Token.ValueString())
    if err != nil {
        resp.Diagnostics.AddError("Unable to create API client", err.Error())
        return
    }
    // Make the client available to resources/data sources.
    resp.ResourceData = client
    resp.DataSourceData = client
}
```

- Provider attributes hold connection config, conventionally settable by
  both HCL and `EXAMPLE_*` environment variables (checked in
  `Configure`, not the schema).
- `resp.ResourceData`/`resp.DataSourceData` is how the configured client
  reaches CRUD methods.
- `Sensitive: true` on credentials; prefer native write-only/ephemeral
  attributes when available so secrets stay out of state.

## Attribute kinds

Every attribute is one of a small set of types:

| Kind | Go value type |
| --- | --- |
| `schema.StringAttribute` | `types.String` |
| `schema.Int64Attribute` | `types.Int64` |
| `schema.Float64Attribute` | `types.Float64` |
| `schema.BoolAttribute` | `types.Bool` |
| `schema.ListAttribute` / `SetAttribute` / `MapAttribute` | `types.List`/`Set`/`Map` |
| `schema.SingleNestedAttribute` / `ListNestedAttribute` / ... | nested object(s) |
| `schema.DynamicAttribute` | `types.Dynamic` |

Use the Framework's `types.*` wrappers (not `*string`/`*int`), because
they carry Terraform's null/unknown distinction. `types.StringNull()`,
`types.StringValue("x")`, `types.StringUnknown()`.

## Required / Optional / Computed

Valid combinations:

| | Meaning |
| --- | --- |
| `Required` | user must set it |
| `Optional` | user may set it |
| `Computed` | server sets it; user must not |
| `Optional` + `Computed` | user may set, server may default/change |
| `Required` + `Computed` | invalid |
| `Optional` + `Required` | invalid |

For a value the server assigns when omitted (like an id), use
`Computed` alone, or `Optional: true, Computed: true` when the user can
choose.

## Validators

```go
import "github.com/hashicorp/terraform-plugin-framework-validators/stringvalidator"

Validators: []validator.String{
    stringvalidator.LengthBetween(1, 63),
    stringvalidator.RegexMatches(regexp.MustCompile(`^[a-z0-9-]+$`), "must be lowercase"),
}
```

- Validators run at plan time against known values and produce
  attribute-attributed errors — much better UX than an API error during
  apply.
- Validators for collections can validate each element
  (`listvalidator.ValueStringsAre(...)`).
- Use `validator.ConfigValidator` for cross-attribute rules.

## Plan modifiers

```go
"id": schema.StringAttribute{
    Computed:     true,
    PlanModifiers: []planmodifier.String{
        stringplanmodifier.UseStateForUnknown(),
    },
},
"force_new": schema.StringAttribute{
    Optional:     true,
    PlanModifiers: []planmodifier.String{
        stringplanmodifier.RequiresReplace(),
    },
},
```

- `UseStateForUnknown()` stops a computed value from showing
  `(known after apply)` on every plan when it won't actually change.
- `RequiresReplace()` when the underlying API can't update the field.
- Custom plan modifiers can express "replace only if X changes".
- Defaults: Framework v1.13+ supports `stringdefault.StaticString(...)`
  and friends as validators/modifiers, avoiding a custom
  `Optional+Computed` dance.

## Getting/Setting state

In CRUD methods:

```go
var plan widgetModel
resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)

// ... call API, build updated model ...

resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
```

- Read the **plan** in Create/Update; read **state** in Read/Delete.
- Model structs use `tfsdk` tags matching the attribute names:

  ```go
  type widgetModel struct {
      ID   types.String `tfsdk:"id"`
      Name types.String `tfsdk:"name"`
      Tags types.Map    `tfsdk:"tags"`
  }
  ```

- After Create, set `id` into the model before `State.Set`.
