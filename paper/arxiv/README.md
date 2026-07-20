# USS / WorldEpisode arXiv LaTeX Template

This directory contains the arXiv-ready LaTeX paper source.

## Build

Two paper variants exist:

- **Anonymous submission** (default): official conference style with anonymous authors.
- **Preprint**: official preprint style with the author block.

Both variants regenerate `generated/experiment_values.tex` from the committed JSON experiment
reports before LaTeX runs. Missing required measurements fail the build. Results for unfinished
gates are shown as `Not defined yet`.

Generate the public publication PDF at the repository root:

```bash
cd paper/arxiv
make root-pdf
```

Generate the named preprint PDF at the repository root:

```bash
cd paper/arxiv
make preprint-pdf
```

Generate both variants:

```bash
cd paper/arxiv
make pdfs
```

Fallback if `make` is unavailable (anonymous build without `latexmk`):

```bash
python3 ../../tools/paper_experiment_values.py
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## arXiv Notes

- Keep all source files under this directory for upload.
- `main.tex` is the entry point.
- `references.bib` is the BibTeX database.
- `submission_config.json` records the target venue and the pinned provisional author-kit baseline.
- Section files live in `sections/`.
- `generated/experiment_values.tex` is generated and must not be edited manually.
- Generated files such as `.aux`, `.bbl`, `.log`, and `paper/arxiv/main.pdf` should not be committed.
- The release PDF `WorldEpisode.pdf` at the repository root is the anonymous submission build.
- Run `python3 ../../tools/neurips_submission_audit.py --strict` before packaging a submission.
- Before uploading source, replace the provisional 2026 style with the official 2027 files when
  they become available, update `submission_config.json`, and remove identifying source metadata.
