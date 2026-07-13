# Famous Benchmark Policy Rerun

Benchmark: `droid`.

Available: `False`.

This artifact is the benchmark-specific evidence record consumed by
`tools/benchmark_inflation_gate.py`. It is fail-closed: unavailable data, proxy lineage, or a
non-published policy protocol must not unlock a published-score inflation claim.

## Result

- Baseline score: `None`
- Corrected score: `None`
- Score drop: `None`
- Lineage source: `None`
- Lineage sufficient for score-inflation claim: `None`

## Boundary

No benchmark inflation claim is supported because the rerun did not execute.

Unavailable reason:

```text
could not download meta/info.json: attempt 1: ConnectionError: HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /datasets/lerobot/droid_100/resolve/87301a2d2e99340e2010c9ef0f1d8e780b08aaf9/meta/info.json (Caused by NameResolutionError("HTTPSConnection(host='huggingface.co', port=443): Failed to resolve 'huggingface.co' ([Errno -3] Temporary failure in name resolution)")) | attempt 2: ConnectionError: HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /datasets/lerobot/droid_100/resolve/87301a2d2e99340e2010c9ef0f1d8e780b08aaf9/meta/info.json (Caused by NameResolutionError("HTTPSConnection(host='huggingface.co', port=443): Failed to resolve 'huggingface.co' ([Errno -3] Temporary failure in name resolution)")) | attempt 3: ConnectionError: HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /datasets/lerobot/droid_100/resolve/87301a2d2e99340e2010c9ef0f1d8e780b08aaf9/meta/info.json (Caused by NameResolutionError("HTTPSConnection(host='huggingface.co', port=443): Failed to resolve 'huggingface.co' ([Errno -3] Temporary failure in name resolution)")) | attempt 4: ConnectionError: HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /datasets/lerobot/droid_100/resolve/87301a2d2e99340e2010c9ef0f1d8e780b08aaf9/meta/info.json (Caused by NameResolutionError("HTTPSConnection(host='huggingface.co', port=443): Failed to resolve 'huggingface.co' ([Errno -3] Temporary failure in name resolution)")) | attempt 5: ConnectionError: HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /datasets/lerobot/droid_100/resolve/87301a2d2e99340e2010c9ef0f1d8e780b08aaf9/meta/info.json (Caused by NameResolutionError("HTTPSConnection(host='huggingface.co', port=443): Failed to resolve 'huggingface.co' ([Errno -3] Temporary failure in name resolution)"))
```
