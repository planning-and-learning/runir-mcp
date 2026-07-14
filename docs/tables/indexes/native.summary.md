# Index Table: native `summary.*`

Used by native proof/classifier/termination-style runs that go through `pyrunir_mcp.output.run`.

| Column | Meaning |
|---|---|
| `id` | Stable item id, also the `failures/<id>/` directory name for failures. |
| `category` | Item category, such as `open_state`, `deadend`, `cycle`, `false_positive`, `false_negative`, or `structural_termination`. |
| `subject` | Problem file or module associated with the item. |
