.PHONY: verify validate

verify: validate

validate:
	python3 scripts/validate.py
