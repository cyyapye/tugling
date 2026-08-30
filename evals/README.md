# Routing fixtures

`routing.json` records one positive, one negative, and one holdout prompt for every shipped skill. `make verify` checks coverage and schema.

These fixtures make trigger intent reviewable, but they do not claim model behavior. For a consequential skill change, run the same blinded prompts against the current and candidate versions, score observable decisions, and record the result before promotion.
