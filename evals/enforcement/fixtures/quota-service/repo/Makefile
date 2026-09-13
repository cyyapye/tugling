.PHONY: test verify

PYTHON ?= python3
TEST_ARGS ?= discover -s tests

test:
	$(PYTHON) -m unittest $(TEST_ARGS)

verify: test
