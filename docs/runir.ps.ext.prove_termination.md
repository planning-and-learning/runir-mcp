# runir.ps.ext.prove_termination

Checks structural termination of an extended module program.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `module_program_file` | string | required | Extended module program file. |
| `output_dir` | string | required | Directory for normalized termination artifacts. |

## Output

Uses the shared counterexample summary format. Nontermination witnesses are structural graph witnesses, not planning-state traces. They are stored in counterexample files and normally do not create `traces/` files.

```json
{
  "tool": "runir.ps.ext.prove_termination",
  "status": "failure",
  "primary": {
    "successful": false,
    "program_status": "NON_TERMINATING",
    "nonterminating_modules": ["main"],
    "prompt_summary": {}
  },
  "items": [
    {
      "category": "structural_termination",
      "path": "<output-dir>/counterexamples/structural_termination/structural_termination-001.json",
      "trace_available": false
    }
  ]
}
```

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  summary.json
  summary.md
  raw/stdout.txt
  raw/stderr.txt
  counterexamples/structural_termination/<id>.json
```
