# Dictionary Table Definitions

Each file in this directory describes one emitted run-global dictionary table.

## Design Differences

The dictionary designs are related but not identical across the output families:

| Family | Dictionaries | Design note |
|---|---|---|
| Base sketch policy | [`features.*`](runir.ps.base.features.md), [`rules.*`](runir.ps.base.rules.md), [`actions.*`](runir.ps.base.actions.md), [`atoms.*`](runir.ps.base.atoms.md) | Policy features drive state columns; rules/actions/atoms are referenced from traces, witnesses, successor frontiers, and plan traces. `atoms.*` includes static atoms but `[facts]` does not repeat them. |
| Module program | [`features.*`](runir.ps.ext.features.md), [`rules.*`](runir.ps.ext.rules.md), [`actions.*`](runir.ps.ext.actions.md), [`atoms.*`](runir.ps.ext.atoms.md), [`modules.*`](runir.ps.ext.modules.md), [`memory.*`](runir.ps.ext.memory.md) | Ext adds module/memory control. Rules are richer than base because they carry source/target memory aliases. `atoms.*` includes static atoms but `[facts]` does not repeat them. |
| Unsolvability classifier | [`features.*`](runir.uns.features.md), [`atoms.*`](runir.uns.atoms.md) | Reduced schema: no rules/actions/memory; features are boolean classifier inputs; atoms include static/fluent/derived atoms seen in checked states, while `[facts]` lists only per-state fluent/derived aliases. |
| Structural termination | [`variables.*`](runir.ps.ext.termination.variables.md), [`memory.*`](runir.ps.ext.termination.memory.md), [`rules.*`](runir.ps.ext.termination.rules.md) | Separate abstract graph schema: variables replace planning features, and there are no planning states, actions, or atoms. |

The `actions.*` table has the same column shape in base and ext, but it is documented separately because the owning output families have different surrounding schemas. The `atoms.*` and `features.*` names recur across families, but their domains differ enough that separate files are clearer.
