# Slipway delivery library

Shared vocabulary and contracts for the Slipway delivery model: an Owner writes one product line and
approves the vision a top-tier model drafts from it; the factory then plans releases, builds toward
their outcomes, validates release candidates and promotes them, with every forward decision made by
a seat that did not do the work.

| File | What it holds |
| --- | --- |
| `terms.yaml` | Canonical terms, the words to avoid for each, naming patterns and status vocabularies. |
| `schemas/defs.json` | ID patterns (`bog/0.2/O1`), the title rule that bans `milestone`, `epic` and `sprint`, and text limits. |
| `schemas/vision.schema.json` | The vision the Owner approves at G0. |
| `schemas/release.schema.json` | The release plan the Release Board approves at G1; its hash is the release's criteria hash. |
| `schemas/board-verdict.schema.json` | The Release Board's approve-or-reject verdict. |

The canonical schemas reference `defs.json` with `$ref`. Packs render self-contained copies with
every `$ref` inlined, so Slipway's step-output validation and agent-side validation enforce the same
rules. bog-factory renders them with `scripts/render_library.py`.

Model providers that enforce structured output usually accept only a subset of JSON Schema (no
`pattern`, length or count limits). Tools derive that strict subset from these schemas for the model
call and then validate the result against the full schema, so the limits still hold.
