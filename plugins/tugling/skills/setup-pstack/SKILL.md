---
name: setup-pstack
description: "Configure Pstack model and reasoning preferences for Codex using available controls. Use for setup-pstack, Pstack budget, or requested model choices."
---

# Setup pstack

Read the [Codex adapter](../poteto-mode/references/codex.md). This retains Pstack's
model/budget setup entry point; project bootstrap is a poteto-mode workflow.

1. Inspect the current session's supported model and reasoning controls. Inherit
   its settings unless the user asked to change them. Never guess a model slug.
2. Infer the requested scope: this task, delegated roles, or a persistent default.
   Explain quality, latency, and usage tradeoffs without claiming an unmeasured
   per-role winner. Offer supported choices only when a choice is still needed.
3. Apply requested settings through an available supported control. If none can
   make the change, say so and give the documented user action. Do not write a
   Cursor model rule or invent a Codex per-role configuration schema.
4. Report which settings actually changed and which remain inherited. Distinguish
   a recommendation from an applied configuration.
5. If the project lacks a way to drive the actual app and the task needs one,
   use [create-verification-skill](../create-verification-skill/SKILL.md) within the
   requested scope. Reuse existing native checks first.
