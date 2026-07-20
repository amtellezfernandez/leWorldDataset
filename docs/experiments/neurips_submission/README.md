# NeurIPS Submission Format Audit

Status: `provisional_ready_pending_target_author_kit`.

The NeurIPS 2027 author kit is not treated as final until both its instructions and
style are recorded in `paper/arxiv/submission_config.json`. The current checks use the official
NeurIPS 2026 Evaluations & Datasets requirements as a provisional baseline.

## Format Boundary

- Review mode: `double_blind`
- Configured style: `paper/arxiv/neurips_2026.sty`
- Target requirements final: `False`
- Style migration required: `True`
- Main-content last page: `9`
- Provisional main-content page limit: `9`
- References page: `10`
- Appendix page: `12`
- Checklist page: `14`
- Total PDF pages: `21`

## Automated Checks

| Check | Pass |
|---|---:|
| `configuration_schema_valid` | True |
| `configured_style_digest_matches` | True |
| `default_build_uses_configured_double_blind_style` | True |
| `manual_margin_and_font_overrides_absent` | True |
| `paper_source_order_is_body_references_appendix_checklist` | True |
| `paper_pdf_is_letter_sized` | True |
| `paper_pdf_author_metadata_is_empty` | True |
| `paper_and_supplement_anonymity_audit_passes` | True |
| `required_pdf_boundaries_are_detected` | True |
| `main_content_fits_provisional_page_limit` | True |
| `conclusion_precedes_references` | True |
| `references_precede_appendix` | True |
| `appendix_precedes_checklist` | True |
| `checklist_is_last` | True |

## External Tasks

| Task | Status | Requirement |
|---|---|---|
| `FORMAT.2027` | `pending_author_kit` | Replace the provisional style and re-audit the page limit and checklist against the official NeurIPS 2027 author kit. |
| `PORTAL.CODE` | `pending_submission_portal` | Provide reviewers a documented, executable, anonymous code URL in the submission form. |
| `ETHICS.2027` | `pending_author_review` | Complete the author ethics attestation against the NeurIPS 2027 Code of Ethics. |

## Validation Errors

- None
