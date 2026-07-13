.PHONY: validate experiments paper readiness check

validate:
	python3 tools/validate_examples.py
	python3 -m py_compile tools/*.py worldepisode/*.py

experiments:
	python3 tools/run_experiments.py

paper:
	$(MAKE) -C paper/arxiv root-pdf

readiness:
	python3 tools/release_readiness.py --strict-rfc

check: validate experiments paper readiness
