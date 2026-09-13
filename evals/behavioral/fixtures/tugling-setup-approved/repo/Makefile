.PHONY: bootstrap dev test verify clean
bootstrap:
	@echo 'Bootstrap is not implemented.' >&2
	@exit 1

dev:
	python3 -m hello_world --name Example

test:
	python3 -m unittest discover -s tests

verify: test

clean:
	python3 -c "from pathlib import Path; [p.unlink() for parent, pattern in ((Path('__pycache__'), 'hello_world.*.pyc'), (Path('tests/__pycache__'), 'test_greeting.*.pyc')) if not parent.is_symlink() for p in parent.glob(pattern) if p.is_file() and not p.is_symlink()]"
