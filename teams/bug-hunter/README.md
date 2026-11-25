# Continuous Bug Hunter Team Pack

Perpetual black-box QA, fuzzing, and bug-triage team powered by Slipway's `WorkflowSchedule` (`Continuous` mode with `carryForwardOutput: true`) and a non-Git `PathLease` scope.

## Pipeline

1. **`hunt`** (`hunter` seat) — Reviews `priorCycle` findings to avoid duplicate testing, picks a new high-risk surface (concurrency, malformed inputs, crash/restart, resource exhaustion, boundary cases), and reports candidate issues (`hunt.json`).
2. **`repro-check`** (trusted `Verifier` Job) — Executes deterministic black-box regression and stress probes pinned by digest, receiving the candidate target and focus area via `inputsFrom`.
3. **`triage`** (`triager` seat) — Deduplicates, ranks severity, records minimal reproduction steps, and emits the structured report (`triage.json`) carried forward into the next cycle as `priorCycle.output`.

## Usage

```sh
NAMESPACE=kagent \
TEAM_NAME=bug-hunter \
TARGET_SCOPE=staging/app \
MODEL_CONFIG=my-model \
VERIFIER_IMAGE=ghcr.io/example/blackbox-runner@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
./scripts/render-team.sh teams/bug-hunter --apply
```
