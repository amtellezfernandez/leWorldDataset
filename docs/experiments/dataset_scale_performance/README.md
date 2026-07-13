# Dataset-Scale Performance Benchmark

Status: pass

This artifact measures catalog-side behavior for a generated large WorldEpisode dataset catalog.
It does not materialize episode rows or payload bytes.

- Trace shards: 32768
- Described episode capacity: 1073741824
- Episodes materialized: 0
- Asset descriptors: 32779
- JSON catalog bytes opened: 24588169
- Generated catalog SHA-256: `11a190f76a6b5c29401aee5e6fd07952ac94ce7a91a117ee8920a081ac65e861`

## Timings

| Operation | Milliseconds |
|---|---:|
| Catalog open, parse, and index | 152.972 |
| Partition-pruning queries | 0.175 |
| Digest-cache resolution | 8.587 |
| Resolver routing | 57.092 |

## Partition Pruning

- Query count: 8
- Max candidate shards after pruning: 3
- Max reduction ratio: 9.155e-05
- All queries pruned: True

## Digest Cache

- Cache hit rate: 0.749992
- Cache hits: 24584
- Cache misses: 8195
- Digest mismatches: 0

## Resolver Routing

| Scheme | Assets |
|---|---:|
| `hf` | 6558 |
| `ipfs` | 6555 |
| `oci` | 6555 |
| `relative` | 6555 |
| `s3` | 6556 |

- Missing resolver count: 0

Boundary: This benchmark measures catalog-side behavior for a generated billion-episode-capacity descriptor set. It does not materialize a billion episode rows, load payload bytes, measure network storage, or prove multi-institution production throughput.
