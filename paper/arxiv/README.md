# WorldEpisode arXiv LaTeX Template

This directory contains the arXiv-ready LaTeX paper source.

## Build

Preferred:

```bash
cd paper/arxiv
make
```

Equivalent:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Fallback if `latexmk` is unavailable:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## arXiv Notes

- Keep all source files under this directory for upload.
- `main.tex` is the entry point.
- `references.bib` is the BibTeX database.
- Section files live in `sections/`.
- Generated files such as `.aux`, `.bbl`, `.log`, and `.pdf` should not be committed.
