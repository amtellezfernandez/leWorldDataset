TEX=main
ROOT_PDF=../../WorldEpisode.pdf

.PHONY: all root-pdf clean distclean

all:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error $(TEX).tex; \
	else \
		pdflatex -interaction=nonstopmode -halt-on-error $(TEX).tex && \
		bibtex $(TEX) && \
		pdflatex -interaction=nonstopmode -halt-on-error $(TEX).tex && \
		pdflatex -interaction=nonstopmode -halt-on-error $(TEX).tex; \
	fi

root-pdf: all
	cp $(TEX).pdf $(ROOT_PDF)

clean:
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -C $(TEX).tex; \
	else \
		rm -f $(TEX).aux $(TEX).bbl $(TEX).bcf $(TEX).blg $(TEX).fdb_latexmk \
			$(TEX).fls $(TEX).log $(TEX).out $(TEX).run.xml $(TEX).synctex.gz \
			$(TEX).pdf; \
	fi

distclean: clean
	rm -f $(ROOT_PDF)
