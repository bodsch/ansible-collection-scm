#
export TOX_SCENARIO  ?= default
export TOX_ANSIBLE   ?= ansible_6.1

export COLLECTION_NAMESPACE ?= bodsch
export COLLECTION_NAME      ?= scm

.PHONY: install uninstall doc converge destroy verify lint

default: install

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

lint:
	@hooks/lint
