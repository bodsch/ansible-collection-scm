#
export COLLECTION_NAMESPACE ?= bodsch
export COLLECTION_NAME      ?= scm
export COLLECTION_ROLE      ?=
export COLLECTION_SCENARIO  ?= default

.PHONY: install uninstall doc converge destroy verify test lint gh-clean

default: converge

install:
	@hooks/install

uninstall:
	@hooks/uninstall

doc:
	@hooks/doc

converge:
	@hooks/converge

destroy:
	@hooks/destroy

verify:
	@hooks/verify

test:
	@hooks/test

lint:
	@hooks/lint

gh-clean:
	@hooks/gh-clean
