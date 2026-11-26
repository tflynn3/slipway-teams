# Slipway Teams

Reusable agent team packs, workflow recipes, schemas, and MCP bridges for [Slipway](https://github.com/tflynn3/slipway) and [kagent](https://github.com/kagent-dev/kagent).

Slipway keeps its core control plane domain-agnostic (`AgentSet`, `WorkflowRun`, `WorkflowBacklog`, `WorkflowSchedule`, `Verifier`, `PathLease`). This repository packages opinionated, ready-to-customize agent teams and tool bridges on top of those primitives so you can stand up a working team in minutes instead of writing hundreds of lines of manifests from scratch.

## Team Packs

| Pack | Purpose | Primitives Used |
|---|---|---|
| [`teams/software-factory`](teams/software-factory) | Continuous & backlog-driven autonomous software development with dual-model separation (architect/reviewer/QA + parallel builders), trusted black-box verification, and PR-Agent review overlay | `AgentSet`, `WorkflowBacklog`, `WorkflowSchedule`, `Verifier`, immutable `schemaFrom` ConfigMaps, `PathLease` |
| [`teams/sre-rollout`](teams/sre-rollout) | Non-Git recurring canary & rollout validation (`observe` → deterministic SLO `verify` probe → `evaluate` → guarded `remediate`) | `AgentSet`, `WorkflowSchedule` (`Interval`), `Verifier`, non-Git `scope` lease, `inputsFrom` |
| [`teams/bug-hunter`](teams/bug-hunter) | Continuous black-box bug hunting, deterministic reproduction, and triage carrying findings across cycles | `AgentSet`, `WorkflowSchedule` (`Continuous`, `carryForwardOutput: true`), `Verifier`, non-Git `scope` lease |
| [`teams/autonomous-org`](teams/autonomous-org) | Executive leadership council (`research` → `pm` → `architect` → `recruit`) that continuously builds the roadmap, makes architecture/infra decisions, and dynamically recruits specialist `AgentTemplate`s + `AgentSet`s | `AgentSet`, `WorkflowSchedule` (`Continuous`, `carryForwardOutput: true`), immutable `schemaFrom` ConfigMaps, `inputsFrom`, non-Git `scope` lease |

## MCP Bridges

| Bridge | Purpose |
|---|---|
| [`bridges/codex-mcp`](bridges/codex-mcp) | Host or sidecar Streamable HTTP MCP bridge wrapping the Codex CLI for multi-model teams (e.g., high-reasoning design/review/QA model + fast implementation model) |
| [`bridges/pr-agent-mcp`](bridges/pr-agent-mcp) | Containerized Streamable HTTP MCP bridge wrapping [The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent) (`PlainDiffGitProvider` + `--json-output`) as a deterministic Slipway review gate |

## Quick Start

### Prerequisites

- A Kubernetes cluster with **kagent `v1alpha3`** and **Slipway** installed (with `Verifier`, `WorkflowSchedule`, and `output.schemaFrom` CRDs enabled).
- `kubectl` configured for your cluster, plus a kagent `ModelConfig` in your target namespace (default: `default-model`).

### Render or Apply a Team Pack

Preview a rendered team pack with your own namespace, repository, verifier digest, and model config:

```sh
NAMESPACE=kagent \
MODEL_CONFIG=my-model \
VERIFIER_IMAGE=ghcr.io/example/slo-probe@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
./scripts/render-team.sh teams/sre-rollout
```

Apply directly to your cluster:

```sh
NAMESPACE=kagent \
MODEL_CONFIG=my-model \
VERIFIER_IMAGE=ghcr.io/example/slo-probe@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
./scripts/render-team.sh teams/sre-rollout --apply
```

For the software factory with a Codex dual-model overlay or PR-Agent reviewer overlay:

```sh
NAMESPACE=kagent \
MODEL_CONFIG=my-model \
REPO_URL=http://git.kagent.svc.cluster.local/app.git \
GIT_SECRET=app-git-credentials \
VERIFIER_IMAGE=ghcr.io/example/app-verifier@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
./scripts/render-team.sh teams/software-factory --overlay codex-dual-model --apply
```

## Authoring a New Team Pack

Every team pack follows the same composable structure:

1. **`schemas.yaml`** — One immutable `ConfigMap` holding every step's JSON Schema so recipes reference them via `output.schemaFrom` instead of repeating inline schemas.
2. **`agents.yaml` / `agentset.yaml`** — Portable kagent `AgentTemplate`s, `Agent`s, and a Slipway `AgentSet` defining seat replicas and `resetPolicy` (`Never` for long-horizon planners, `OnFailure` for builders, `AfterAssignment` for fresh reviewers/QA).
3. **`verifier.yaml`** — Cluster-scoped Slipway `Verifier` CR pinning the deterministic verification container by `@sha256:` digest with namespace scoping.
4. **`recipe.yaml` / `recipes.yaml`** — Immutable recipe `ConfigMap`s for `WorkflowBacklog` and `WorkflowSchedule`.
5. **`schedule.yaml`** — A `WorkflowSchedule` driving the team on an `Interval` or `Continuous` cadence.
6. **`overlays/`** (optional) — Swappable model or tool-bridge overlays (e.g., Codex CLI, PR-Agent, or custom MCP servers).

## Validation

Run local syntax and manifest validation:

```sh
make validate
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
