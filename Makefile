.PHONY: verify validate test eval-validate clean-room-validate release-validate

verify: validate test eval-validate clean-room-validate release-validate

validate:
	python3 scripts/validate.py

test:
	python3 -m unittest discover -s tests

eval-validate:
	python3 scripts/behavioral_eval.py validate

clean-room-validate:
	python3 scripts/clean_room_install.py validate

release-validate:
	python3 scripts/release_gate.py validate
