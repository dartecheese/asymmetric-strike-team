# =============================================================================
#  Asymmetric Strike Team — Makefile
#
#  Quick tasks for the Grinding Wheel.
# =============================================================================

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
VENV_PYTHON := $(PROJECT_DIR)/.venv/bin/python3

.PHONY: install install-service uninstall status run once clean test help

install:        ## Install grind CLI (symlink to ~/.local/bin)
	$(PROJECT_DIR)/install.sh

install-service: ## Install CLI + LaunchAgent background service
	$(PROJECT_DIR)/install.sh --service

uninstall:      ## Remove CLI + LaunchAgent service
	$(PROJECT_DIR)/install.sh --uninstall

status:         ## Check installation status
	$(PROJECT_DIR)/install.sh --status

once:           ## Run a single pipeline turn
	$(VENV_PYTHON) $(PROJECT_DIR)/grind.py --once

run:            ## Start interactive loop mode
	$(VENV_PYTHON) $(PROJECT_DIR)/grind.py

rules:          ## Run with rules-based agents (no AI)
	$(VENV_PYTHON) $(PROJECT_DIR)/grind.py --no-model --once

logs:           ## Tail the service logs
	tail -f $(PROJECT_DIR)/logs/grind-stdout.log

clean:          ## Remove cached model data
	rm -rf $(PROJECT_DIR)/__pycache__ $(PROJECT_DIR)/**/__pycache__
	rm -rf $(PROJECT_DIR)/.venv/lib/python3.14/site-packages/mlx_community* 2>/dev/null || true
	@echo "Cache cleaned. Models still cached in ~/.cache/huggingface/"

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
