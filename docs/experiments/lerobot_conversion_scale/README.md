# LeRobot Conversion Scale

Status: `pass`.

Every episode assigned to one immutable LeRobot v3 source Parquet file per dataset; no episode-level sampling.

| Dataset subset | Episodes | State/action rows | Video streams | Wall time (s) | Peak RSS (MiB) | Max error |
|---|---:|---:|---:|---:|---:|---:|
| `svla_so101_pickplace` | 50 | 11939 | 2 | 4.529 | 336.4 | 0.0 |
| `pusht` | 206 | 25650 | 1 | 29.202 | 162.5 | 0.0 |
| `armnetbench_file_000` | 15 | 6012 | 3 | 14.121 | 393.3 | 0.0 |

## Aggregate

- Datasets: 3
- Multi-camera datasets: 2
- Episodes: 271
- State/action rows: 43601
- Source input bytes: 5485027
- Temporary converted bytes: 18354903
- Maximum numerical error: 0.0
- Unique source-absent semantic fields: 4
- Worker wall time: 47.851 s
- Maximum worker RSS: 393.3 MiB

Video stream metadata is retained in the sidecar, but source video payloads are neither downloaded
nor redistributed. Temporary converted packages are deleted after exact comparison.

## Claim Boundary

This measures exact low-dimensional LeRobot/WorldEpisode conversion over complete pinned Parquet shards. It does not convert video payload bytes, prove full-corpus throughput, or evaluate policy quality.

## Validation Errors

- None
