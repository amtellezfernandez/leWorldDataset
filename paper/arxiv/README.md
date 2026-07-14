# USS / WorldEpisode arXiv LaTeX Template

This directory contains the arXiv-ready LaTeX paper source.

## Build

Two builds exist:

- **Publication build** (default): strips the collaborator Open Contributions appendix and the
  inline HELP markers by defining `\collaboff` on the command line.
- **Collab build**: the working build with the C1--C7 task cards and HELP markers, for
  collaborators picking up open experiments.

Generate the public publication PDF at the repository root:

```bash
cd paper/arxiv
make root-pdf
```

Generate the collaborator working PDF at the repository root:

```bash
cd paper/arxiv
make collab-pdf
```

Generate both (`WorldEpisode-collab.pdf` first, then `WorldEpisode.pdf`):

```bash
cd paper/arxiv
make pdfs
```

Fallback if `make` is unavailable (publication build without `latexmk`):

```bash
pdflatex '\def\collaboff{}\input{main.tex}'
bibtex main
pdflatex '\def\collaboff{}\input{main.tex}'
pdflatex '\def\collaboff{}\input{main.tex}'
```

Omit the `\def\collaboff{}` prefix for the collab build.

## arXiv Notes

- Keep all source files under this directory for upload.
- `main.tex` is the entry point.
- `references.bib` is the BibTeX database.
- Section files live in `sections/`.
- Generated files such as `.aux`, `.bbl`, `.log`, and `paper/arxiv/main.pdf` should not be committed.
- Upload the **publication build** source state to arXiv (the `\collaboff` define is a build-time
  flag, so the same source tree works; just do not upload a PDF built with the collab appendix).
- The release PDF `WorldEpisode.pdf` (publication build) and the collaborator working PDF
  `WorldEpisode-collab.pdf` at the repository root are intentionally committed. The paper title is
  "WorldEpisode: Auditing Silent State Drift in Robot-Learning Datasets"; the filenames remain
  stable for repository links.
