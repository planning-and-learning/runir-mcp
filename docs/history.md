# Validation History

`ValidationHistory` is caller-owned state. Validation calls return observations, but they do not
mutate history automatically.

## `ValidationHistory`

```python
history = ValidationHistory()
feedback = history.fold(result.observation)
```

| Field | Type | Description |
|---|---|---|
| `observations` | `list[ValidationObservation]` | Observations folded so far. |

`fold(observation)` appends the observation and returns `HistoryFeedback`.

## `HistoryFeedback`

| Field / property | Type | Description |
|---|---|---|
| `observation` | `ValidationObservation` | The folded observation. |
| `previous_occurrences` | `int` | Number of previous observations with the same fingerprint/key. |
| `total_observations` | `int` | Number of observations after folding. |
| `repeated` | `bool` | `True` when `previous_occurrences > 0`. |

When a validation observation has a `FailureFingerprint`, history compares fingerprints. Otherwise
it falls back to validation kind, status, candidate ID, and classifier ID.

## Dumping

Use `dump_validation_history(history, output_dir)` when another process needs the history on disk.
