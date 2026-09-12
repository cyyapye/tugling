# Existing greeting CLI

`python3 -m hello_world --name Ada` prints `Hello, Ada!`. The native test command
works, but bootstrap fails and Codex local-environment setup is missing.
Finish this offline Python standard-library workflow with repeatable bootstrap,
dev, test, verify, and cleanup Make targets. Preserve the unittest cases under
`tests/`. Cleanup must remove known project bytecode and preserve user files and
unrelated cache contents.
Prepare the Codex environment as `codex-environment.toml`, with a setup script
calling bootstrap. The CLI sandbox protects `.codex/`; installing this file at
its final `.codex/environments/environment.toml` location is outside this request.
No Tugling adoption adapter, external dependencies, or deployment is required.
