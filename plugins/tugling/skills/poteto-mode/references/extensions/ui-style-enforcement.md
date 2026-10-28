# UI style enforcement

Use when the user requests design-system lint setup or an existing UI adapter
requires it. Assessment stays read-only; backend work and a small copy fix do not
install a linter. Keep stack choices and allowed component styling in the adopter.

## Select and configure the native tool

Inspect the lockfile, Node version, existing lint command/parser/ignores, actual
component imports and theme. For a compatible Tailwind v4 project, use the
official [@shadcn/lint setup](https://github.com/shadcn-ui/lint/blob/main/SETUP.md)
and [rule documentation](https://github.com/shadcn-ui/lint/blob/main/docs/rules.md).
Check the installed version's API; preserve the existing ESLint or Oxlint setup.
Register the plugin in the package that owns the UI lint command and lock the
resolved dependency with the project's package manager. A plugin registration
with no enabled rules proves loading only, not enforcement.

Map accepted project rules to explicit errors. Configure real component import
prefixes, including workspace libraries. Distinguish component implementation
from consumer usage: controls own their appearance; pages may control placement
and documented composition spacing. `no-restyle` contracts must preserve those
intentional extension points. Use `no-arbitrary-values`, `no-raw-colors`,
`no-unknown-classes` or inline-style rules only where the project contract supports
them. Runtime chart dimensions, approved CSS variables and authored utility
classes need deliberate treatment. Do not enable an entire preset, blanket-ignore
existing findings or redesign working screens to make the checker green.

For projects using plain CSS or an unsupported stack, preserve or extend their
existing token/component checks. Do not introduce Tailwind or claim that a
Tailwind-only rule verifies the project's CSS. State exactly which patterns the
chosen checker can inspect.

Scope an incremental rollout explicitly in the project guide and lint config.
Prefer the normal lint command, included in its canonical gate/CI. A narrow pilot
is not repository-wide enforcement. Keep adopted rules and allowed exceptions
in that project's authored guide, with errors pointing agents to the relevant
components, variants and tokens. Repeating setup must not duplicate config.

## Prove the rule, not just configuration loading

1. Run the normal lint command on allowed project code and retain its exit status.
2. In a disposable source file within the configured scope, introduce an actual
   prohibited restyle and another relevant violation. Run the same command and
   assert nonzero status plus the expected rule, file and location. A parse error,
   ignored file or missing plugin is not rule proof.
3. Repair using the shared component API/tokens and rerun to zero violations.
   Keep a legitimate placement/composition exception as a passing control.
4. Remove the probe and replay the project's gate. Record the package version,
   enabled rule policy, scope, commands and before/after outputs.

Include configuration, lockfiles and authored rule inputs in `.tugling/ui.json`
source tracking, and its actual command in `checks`. The evidence helper never
executes that command. Browser behavior/accessibility checks and independent
rendered review remain separate; lint cannot decide whether the interface makes
sense or looks good.
