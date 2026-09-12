# Offline greeting CLI

Bootstrap this new synthetic Python 3 standard-library project for Codex work.
The command `python3 -m hello_world --name Ada` should print `Hello, Ada!`.
Other names, including names with spaces, must work. No network, external
dependencies, service, account, or deployment is needed.

Use project-owned `make bootstrap`, `make dev`, `make test`, `make verify`, and
`make clean`. Bootstrap must work from a fresh checkout and be safe to repeat;
cleanup must remove known project bytecode while preserving source, user files,
and unrelated cache contents. Add concise AGENTS.md, unittest cases under `tests/`,
appropriate ignores, and a prepared Codex environment file `codex-environment.toml`
whose setup script calls bootstrap. The CLI sandbox protects `.codex/`; installation
at `.codex/environments/environment.toml` is deliberately outside this request.
This request covers the native project workflow only, with no Tugling source pin
or adoption CI needed yet. Do not add a plugin copy or unrelated product features.
