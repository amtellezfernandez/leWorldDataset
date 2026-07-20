.PHONY: validate test experiments conversion-scale timing-audit contact-replay policy-compatibility policy-vision-smoke statistics experiment-manifest source-audits paper paper-values supplement submission-format open-gates paper-claims release-manifest verify-release-manifest submission-packet readiness freshness check

validate:
	python3 tools/validate_examples.py
	python3 -m py_compile tools/*.py worldepisode/*.py
	python3 tools/paper_experiment_values.py --check
	python3 tools/lerobot_conversion_scale.py --check --required
	uv run --with pyarrow --with numpy python tools/lerobot_multitrajectory_timing_audit.py --check --required
	python3 tools/contact_rich_cross_sim_replay.py --check --required
	python3 tools/lerobot_policy_compatibility_audit.py --check --strict
	python3 tools/lerobot_policy_video_materialization.py --check --strict
	python3 tools/lerobot_policy_vision_smoke.py --check --strict
	python3 tools/experiment_manifest.py --check --strict
	python3 tools/citation_source_audit.py --check --strict
	python3 tools/third_party_asset_audit.py --check --strict
	python3 tools/build_anonymous_supplement.py --check --strict
	python3 tools/submission_anonymity_audit.py --check --strict
	python3 tools/neurips_submission_audit.py --check --strict

test:
	python3 -m pytest

experiments:
	python3 tools/run_experiments.py
	python3 tools/experiment_statistics.py
	python3 tools/experiment_manifest.py --strict

conversion-scale:
	uv run --with pyarrow --with requests python tools/lerobot_conversion_scale.py --required

timing-audit:
	uv run --with pyarrow --with numpy python tools/lerobot_multitrajectory_timing_audit.py --required

contact-replay:
	UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu uv run --isolated --python 3.11 --index-strategy unsafe-best-match --with 'torch==2.8.0+cpu' --with 'numpy==2.4.6' --with 'mujoco==3.3.7' --with 'genesis-world==1.2.2' python tools/contact_rich_cross_sim_replay.py --required

policy-compatibility:
	python3 tools/lerobot_policy_compatibility_audit.py --check --strict

policy-vision-smoke:
	python3 tools/lerobot_policy_video_materialization.py --check --strict
	python3 tools/lerobot_policy_vision_smoke.py --check --strict

statistics:
	python3 tools/experiment_statistics.py

experiment-manifest:
	python3 tools/experiment_manifest.py --strict

source-audits:
	python3 tools/citation_source_audit.py --strict
	python3 tools/third_party_asset_audit.py --strict

paper:
	$(MAKE) -C paper/arxiv root-pdf

paper-values: statistics source-audits
	python3 tools/paper_experiment_values.py

supplement:
	python3 tools/build_anonymous_supplement.py --strict
	python3 tools/submission_anonymity_audit.py --strict

submission-format:
	python3 tools/neurips_submission_audit.py --strict

open-gates:
	python3 tools/open_reproduction_gates.py --strict

paper-claims:
	python3 tools/paper_claim_audit.py --strict

release-manifest:
	python3 tools/release_manifest.py --strict

verify-release-manifest:
	python3 tools/release_manifest.py --verify --strict

submission-packet: release-manifest
	python3 tools/submission_packet.py --strict

readiness: open-gates paper-claims
	python3 tools/build_anonymous_supplement.py --strict
	python3 tools/submission_anonymity_audit.py --strict
	python3 tools/neurips_submission_audit.py --strict
	python3 tools/release_manifest.py --strict
	python3 tools/submission_packet.py --strict
	python3 tools/release_readiness.py --strict-rfc
	python3 tools/build_anonymous_supplement.py --strict
	python3 tools/submission_anonymity_audit.py --strict
	python3 tools/neurips_submission_audit.py --strict
	python3 tools/release_manifest.py --strict
	python3 tools/release_manifest.py --verify --strict
	python3 tools/submission_packet.py --strict
	python3 tools/release_readiness.py --strict-rfc
	python3 tools/build_anonymous_supplement.py --check --strict
	python3 tools/submission_anonymity_audit.py --check --strict

freshness:
	python3 tools/artifact_freshness.py --strict

check: experiments experiment-manifest source-audits paper-values paper readiness validate
