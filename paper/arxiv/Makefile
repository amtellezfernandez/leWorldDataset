TEX=main

.PHONY: all clean

all:
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(TEX).tex

clean:
	latexmk -C $(TEX).tex

