# SRE Rollout Validation Team Pack

Non-Git recurring canary and rollout validation team built on Slipway's `WorkflowSchedule` (`Interval`), non-Git `PathLease` scopes, trusted `Verifier` SLO probes, and `inputsFrom` cross-step wiring.

## Pipeline

1. **`observe`** (`observer` seat) — Collects telemetry, pod health, recent deploys, and log error samples for `__SERVICE_NAME__` and outputs structured JSON (`observation.json`).
2. **`slo-probe`** (trusted `Verifier` Job) — Runs a deterministic, digest-pinned synthetic latency & error-rate probe receiving `revision` and `ring` via `SLIPWAY_PARAM_*` and `SLIPWAY_INPUT_*`.
3. **`evaluate`** (`evaluator` seat) — Evaluates the observation + probe outcome against SLO gates using Slipway CEL `successWhen` (`output.healthy && output.errorRatePct < 1.0`).
4. **`remediate`** (`remediator` seat, optional) — Triggered or invoked when promotion/rollback guidance is needed, coordinated under an `Exclusive` scope `PathLease` (`__TARGET_SCOPE__`) so concurrent rollout checks never collide on the same blast radius.

## Usage

```sh
NAMESPACE=kagent \
TEAM_NAME=sre-rollout \
SERVICE_NAME=checkout \
TARGET_SCOPE=prod/checkout \
MODEL_CONFIG=my-model \
VERIFIER_IMAGE=ghcr.io/example/slo-probe@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
./scripts/render-team.sh teams/sre-rollout --apply
```
