.PHONY: validate experiments paper open-gates paper-claims readiness check

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

readiness: open-gates paper-claims
	python3 tools/release_readiness.py --strict-rfc

check: validate experiments paper readiness
