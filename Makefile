.PHONY: verify validate test eval-validate

verify: validate test eval-validate

validate:
	python3 scripts/validate.py

test:
	python3 -m unittest discover -s tests

eval-validate:
	python3 scripts/behavioral_eval.py validate
