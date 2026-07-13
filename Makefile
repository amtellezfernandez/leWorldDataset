.PHONY: validate experiments paper open-gates paper-claims release-manifest submission-packet readiness freshness check

validate:
	python3 tools/validate_examples.py
	python3 -m py_compile tools/*.py worldepisode/*.py

experiments:
	python3 tools/run_experiments.py

paper:
	$(MAKE) -C paper/arxiv root-pdf

open-gates:
	python3 tools/open_reproduction_gates.py --strict

paper-claims:
	python3 tools/paper_claim_audit.py --strict

release-manifest:
	python3 tools/release_manifest.py --strict

submission-packet: release-manifest
	python3 tools/submission_packet.py --strict

readiness: open-gates paper-claims release-manifest submission-packet
	python3 tools/release_readiness.py --strict-rfc

freshness:
	python3 tools/artifact_freshness.py --strict

check: validate experiments paper readiness
