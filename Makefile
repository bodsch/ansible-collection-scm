#
export COLLECTION_NAMESPACE ?= bodsch
export COLLECTION_NAME      ?= cloud
export COLLECTION_ROLE      ?=
export COLLECTION_SCENARIO  ?= default
export TOX_ANSIBLE          ?= ansible_9.5
# --------------------------------------------------------

# Alle Targets, die schlicht ein Skript in hooks/ aufrufen
HOOKS := install uninstall doc prepare converge destroy verify test lint gh-clean

.PHONY: $(HOOKS)
.DEFAULT_GOAL := converge

# $@ expandiert zu dem Namen des gerade angeforderten Targets
$(HOOKS):
	@hooks/$@
