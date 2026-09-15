# CRUD, state, and diagnostics

## The resource interface

```go
type widgetResource struct{ client *client.Client }

func (r *widgetResource) Metadata(_ context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
    resp.TypeName = req.ProviderTypeName + "_widget"
}

func (r *widgetResource) Schema(ctx context.Context, req resource.SchemaRequest, resp *resource.SchemaResponse) {
    resp.Schema = /* see framework-schema.md */
}

func (r *widgetResource) Configure(ctx context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
    if req.ProviderData == nil { return }
    r.client = req.ProviderData.(*client.Client)
}

func (r *widgetResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) { ... }
func (r *widgetResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) { ... }
func (r *widgetResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) { ... }
func (r *widgetResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) { ... }
```

Register it in the provider's `Resources()`:

```go
func (p *exampleProvider) Resources(ctx context.Context) []func() resource.Resource {
    return []func() resource.Resource{ NewWidgetResource }
}
```

## Create

```go
var plan widgetModel
resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
if resp.Diagnostics.HasError() { return }

created, err := r.client.CreateWidget(ctx, plan.toAPI())
if err != nil {
    resp.Diagnostics.AddError("Error creating widget", err.Error())
    return
}

plan.ID = types.StringValue(created.ID)
plan.Name = types.StringValue(created.Name)
resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
```

Always write the full model (including server-computed fields) to state
after create, so the next plan is clean.

## Read (drift detection)

```go
var state widgetModel
resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
if resp.Diagnostics.HasError() { return }

widget, err := r.client.GetWidget(ctx, state.ID.ValueString())
if errors.Is(err, client.ErrNotFound) {
    resp.State.RemoveResource(ctx)   // gone -> Terraform plans a recreate
    return
}
if err != nil {
    resp.Diagnostics.AddError("Error reading widget", err.Error())
    return
}

state.Name = types.StringValue(widget.Name)
resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
```

`RemoveResource` on not-found is the mechanism for real drift
detection. Without it, Terraform thinks the resource still exists and
`apply` will not recreate it.

## Update

```go
var plan, state widgetModel
resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
// ... call API with plan's values ...
resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
```

- Fields marked `RequiresReplace` never reach Update — Terraform
  destroys and recreates.
- If the API has no partial update, either send the whole object or mark
  the resource `RequiresReplace`-on-any-change (documented tradeoff).

## Delete

```go
var state widgetModel
resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
if err := r.client.DeleteWidget(ctx, state.ID.ValueString()); err != nil {
    if !errors.Is(err, client.ErrNotFound) {   // already gone is success
        resp.Diagnostics.AddError("Error deleting widget", err.Error())
        return
    }
}
```

Best-effort deletes (some registries can't delete, say): log a warning
diagnostic and still let Terraform remove it from state rather than
wedging the plan forever.

## Import

```go
func (r *widgetResource) ImportState(ctx context.Context,
    req resource.ImportStateRequest, resp *resource.ImportStateResponse) {
    resource.ImportStatePassthroughID(ctx, path.Root("id"), req, resp)
}
```

After import, Terraform calls `Read` to populate the rest. For composite
ids (`<parent>/<child>`), split in `ImportState` and set each attribute.
Add an `ImportState` test step to prove it round-trips.

## Diagnostics

Prefer typed diagnostics so failures are attributed:

```go
resp.Diagnostics.AddError(
    "Unable to create widget",
    fmt.Sprintf("The API returned an unexpected error: %s", err),
)
resp.Diagnostics.AddAttributeError(
    path.Root("name"), "Invalid name", "Name must be unique.",
)
```

- `AddError(summary, detail)` — general.
- `AddAttributeError(path, summary, detail)` — points at a field.
- `AddWarning(...)` — non-fatal.
- Check `resp.Diagnostics.HasError()` after every `Get`/`Append` and
  bail out; continuing with a partial model causes confusing failures.

## Timeouts

For long-running operations, use the resource `timeouts` block:

```go
resp.Schema = schema.Schema{
    // ...
    // via resource.Timeouts: { Create: 20*time.Minute, ... }
}
```

Configure per-operation timeouts and honor `ctx` deadline in the client
calls. Don't hardcode sleeps; poll with backoff against the API's own
status.

## State safety

- Don't store secrets in normal attributes if avoidable; Framework
  write-only/ephemeral attributes (or marking `Sensitive`) keep them out
  of plaintext state/plan.
- State is not a secret store — assume it's readable by whoever has the
  backend, and never put credentials there if there's an alternative.
