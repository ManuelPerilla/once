# Optional shortcuts; Python entry points also work on Windows without GNU Make.
PYTHON ?= python
.DEFAULT_GOAL := help
.PHONY: help configure backend-install frontend-install api worker web up down logs health lint test-api test-web build docs-check check qa-up qa-test qa-down ci-local backup benchmark lan local network-status

help configure backend-install frontend-install api worker web up down logs health lint test-api test-web build docs-check check qa-up qa-test qa-down ci-local backup:
	$(PYTHON) -m scripts.dev $@

benchmark:
	$(PYTHON) -m scripts.dev benchmark $(ARGS)

lan local network-status:
	$(PYTHON) -m scripts.dev $@ $(ARGS)
