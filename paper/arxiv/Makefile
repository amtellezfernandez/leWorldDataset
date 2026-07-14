TEX=main
ROOT_PDF=../../WorldEpisode.pdf
COLLAB_PDF=../../WorldEpisode-collab.pdf
# Publication build: define \collaboff so the Open Contributions appendix and
# inline HELP markers are stripped. The collab build omits it.
PUB_PRETEX=\def\collaboff{}
LATEX_RUN=pdflatex -interaction=nonstopmode -halt-on-error

.PHONY: all pub collab root-pdf collab-pdf pdfs clean distclean

all: pub

pub:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error \
			-usepretex='$(PUB_PRETEX)' $(TEX).tex; \
	else \
		$(LATEX_RUN) '$(PUB_PRETEX)\input{$(TEX).tex}' && \
		bibtex $(TEX) && \
		$(LATEX_RUN) '$(PUB_PRETEX)\input{$(TEX).tex}' && \
		$(LATEX_RUN) '$(PUB_PRETEX)\input{$(TEX).tex}'; \
	fi

collab:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error $(TEX).tex; \
	else \
		$(LATEX_RUN) $(TEX).tex && \
		bibtex $(TEX) && \
		$(LATEX_RUN) $(TEX).tex && \
		$(LATEX_RUN) $(TEX).tex; \
	fi

root-pdf: pub
	cp $(TEX).pdf $(ROOT_PDF)

collab-pdf: collab
	cp $(TEX).pdf $(COLLAB_PDF)

# Build both root PDFs; the publication build runs last so main.pdf matches it.
pdfs: collab-pdf root-pdf

clean:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -C $(TEX).tex; \
	else \
		rm -f $(TEX).aux $(TEX).bbl $(TEX).bcf $(TEX).blg $(TEX).fdb_latexmk \
			$(TEX).fls $(TEX).log $(TEX).out $(TEX).run.xml $(TEX).synctex.gz \
			$(TEX).pdf; \
	fi

distclean: clean
	rm -f $(ROOT_PDF) $(COLLAB_PDF)
