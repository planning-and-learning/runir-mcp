# Section Table: module-program `[transitions]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Trace or cycle edges between module-program control states.

| Column | Meaning |
|---|---|
| `step` | Transition index within the trace or cycle. |
| `source_state` | Source planning-state id (`sK`). |
| `source_module` | Source module alias (`MK`). |
| `source_memory` | Source memory-location alias (`mK`). |
| `target_state` | Target planning-state id (`sK`). |
| `target_module` | Target module alias (`MK`). |
| `target_memory` | Target memory-location alias (`mK`). |
| `rule` | Module-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.ext.rules.md). |
| `action` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.ext.actions.md). |
| `delta` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.ext.features.md). |
