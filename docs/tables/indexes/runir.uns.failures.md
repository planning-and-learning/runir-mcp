# Index Table: classifier `failures.*`

Design reference for classifier witness runs.

| Column | Meaning |
|---|---|
| `id` | Stable classifier mistake id, e.g. `false_negative-001`. |
| `category` | Mistake category: `false_positive` or `false_negative`. |
| `problem` | Problem file path/name. |
| `witness` | Relative path to `failures/<id>/witness.*`. |
