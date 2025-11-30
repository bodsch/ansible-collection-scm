#
export COLLECTION_ROLE      ?=
export COLLECTION_SCENARIO  ?= default
export TOX_ANSIBLE          ?= ansible_9.5
export TOX_SILENCE          ?= true
# --------------------------------------------------------

LANG                        := C.UTF-8
TEMP_REPO_URL               := http://git.boone-schulz.de/ansible/ansible-hooks.git
TEMP_REPO_PATH              := collections/hooks
TARGET_DIR                  := hooks
CACHE_DIR                   := $(HOME)/.cache/ansible/ansible-hooks

# --------------------------------------------------------

# Alle Targets, die schlicht ein Skript in hooks/ aufrufen
HOOKS := install uninstall doc prepare converge destroy verify test lint gh-clean
TARGET_DIR := hooks

.SILENT: hooks-ready
.PHONY: $(HOOKS)
.ONESHELL:
.DEFAULT_GOAL := converge

$(HOOKS): | hooks-ready
	@hooks/$@

hooks-ready:
	@if [ ! -d "hooks" ] || [ -z "$$(ls -A 'hooks' 2>/dev/null)" ]; then \
		$(MAKE) --no-print-directory fetch-hooks >/dev/null 2>&1; \
	fi

fetch-hooks:
	@if [ -d "$(CACHE_DIR)/.git" ]; then
		git -C "$(CACHE_DIR)" fetch --depth=1 --prune origin
		def=$$(git -C "$(CACHE_DIR)" remote show origin | awk '/HEAD branch/ {print "origin/"$$NF}')
		git -C "$(CACHE_DIR)" reset --hard "$$def"
	else
		mkdir -p "$(dir $(CACHE_DIR))"
		GIT_TERMINAL_PROMPT=0 git clone --depth 1 "$(TEMP_REPO_URL)" "$(CACHE_DIR)"
	fi
	@mkdir -p "$(TARGET_DIR)"
	@rsync -a --delete "$(CACHE_DIR)/$(TEMP_REPO_PATH)/" "$(TARGET_DIR)/"
