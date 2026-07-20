TEX=main
ROOT_PDF=../../WorldEpisode.pdf
PREPRINT_PDF=../../WorldEpisode-preprint.pdf
PREPRINT_PRETEX=\def\wepreprint{}
LATEX_RUN=pdflatex -interaction=nonstopmode -halt-on-error
PAPER_VALUES=../../tools/paper_experiment_values.py
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct)
export SOURCE_DATE_EPOCH
export FORCE_SOURCE_DATE=1
export TZ=UTC

.PHONY: all values submission pub preprint root-pdf submission-pdf preprint-pdf pdfs clean distclean

all: submission

values:
	python3 ../../tools/experiment_statistics.py
	python3 $(PAPER_VALUES)

submission: values
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error \
			$(TEX).tex; \
	else \
		$(LATEX_RUN) $(TEX).tex && \
		bibtex $(TEX) && \
		$(LATEX_RUN) $(TEX).tex && \
		$(LATEX_RUN) $(TEX).tex; \
	fi

pub: preprint

preprint: values
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error \
			-usepretex='$(PREPRINT_PRETEX)' $(TEX).tex; \
	else \
		$(LATEX_RUN) '$(PREPRINT_PRETEX)\input{$(TEX).tex}' && \
		bibtex $(TEX) && \
		$(LATEX_RUN) '$(PREPRINT_PRETEX)\input{$(TEX).tex}' && \
		$(LATEX_RUN) '$(PREPRINT_PRETEX)\input{$(TEX).tex}'; \
	fi

submission-pdf: submission
	cp $(TEX).pdf $(ROOT_PDF)

root-pdf: submission-pdf

preprint-pdf: preprint
	cp $(TEX).pdf $(PREPRINT_PDF)

# Build all variants; the anonymous submission runs last so main.pdf matches it.
pdfs: preprint-pdf root-pdf

clean:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -C $(TEX).tex; \
	else \
		rm -f $(TEX).aux $(TEX).bbl $(TEX).bcf $(TEX).blg $(TEX).fdb_latexmk \
			$(TEX).fls $(TEX).log $(TEX).out $(TEX).run.xml $(TEX).synctex.gz \
			$(TEX).pdf; \
	fi

distclean: clean
	rm -f $(ROOT_PDF) $(PREPRINT_PDF)
