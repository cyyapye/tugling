# Runnable project bootstrap

Use for a new project or a requested repair of local development setup. The finish
condition is a fresh checkout that can bootstrap, run the smallest real user flow,
verify it, and clean up through project-owned commands.

## Establish the native workflow

Respect a specified stack, runtime, package manager, and product scope. Infer
routine details from existing manifests and nearby conventions. Ask when a missing
choice would materially change the product or cost; a named stack and concrete
starter outcome are enough to begin local work.

Provide only what the project needs:

- A minimal runnable scaffold for the requested flow, with meaningful native tests.
- A declared runtime and reproducible dependency setup, using the native lockfile
  where dependencies exist. An offline standard-library project needs no new dependency.
- Project-owned bootstrap, dev, focused test, verification, and cleanup commands.
  Use the stack's established entry points; Make targets are an option, not a requirement.
- A repeatable bootstrap that detects missing prerequisites and is safe to rerun.
  It must not overwrite developer edits, reset databases, or reinstall shared tools.
- Environment examples containing names and safe placeholders only when needed.
  Keep credentials, generated dependencies, build output, and local data untracked.

Keep changes to an existing project bounded to the requested missing workflow.
Reuse native tests and runtime lifecycle rather than adding a parallel framework.

## Put guidance where it applies

Keep the root `AGENTS.md` short: relevant commands, product/data invariants, safe
local operations, completion criteria, and links with clear reading conditions.
Put specialized instructions in the relevant subdirectory and durable architecture
in its existing docs. Avoid prescribing a full document tour for every edit.

Create a repo-local skill only for a repeated, non-obvious workflow that existing
skills do not own. Use `.agents/skills` for Codex-local discovery. Do not copy generic
Tugling skills or an Astra prompt manual into every project. Keep enforceable
requirements in types, scripts, tests, or CI when appropriate.

## Make fresh worktrees usable

When Codex local setup is part of the request, add or update the project's
`.codex/environments/environment.toml` to call its native bootstrap command and
expose useful dev/verify actions. Reuse its existing configuration. If the schema
is unfamiliar, consult current official documentation instead of guessing fields.

Resolve paths from the checkout rather than an author-specific absolute path.
For concurrent services, use project-owned ports, databases, volumes, and process
ownership. Readiness and teardown belong to the native runner. A CLI with no
persistent service needs no port allocation or background supervisor.

CI should invoke the same native verification contract. Keep it independent of
developer-only files and credentials. Set up local commands before external CI
or provisioning when those require a separate decision or access.

## Prove setup works

Exercise a fresh isolated checkout containing the intended source files, without
ignored dependencies or hidden files from the working directory. For uncommitted
work, use a disposable snapshot that includes intended new files; distinguish
that proof from a clean committed revision. Preserve the user's checkout.

Run bootstrap twice, then invoke a real app or CLI flow and the required native
gate. For material UI work, inspect the resulting interface at the supported
desktop and narrow sizes. Run cleanup and confirm only owned resources were
removed and user source stayed intact. Check that subsequent bootstrap still works.

Check instruction paths, skill discovery locations, and the local-environment
command from the fresh checkout. Distinguish configuration validation, directly
exercised commands, and an observed Codex setup launch; do not infer the last from
the first two. Report missing prerequisites or external access precisely.
