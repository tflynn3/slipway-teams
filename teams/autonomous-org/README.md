# Autonomous Organization Leadership Pack

Higher-level executive council team pack for Slipway + kagent that runs continuously on a `WorkflowSchedule` to research the domain, curate a product roadmap, scope parallel engineering tracks with `PathLease` isolation, and dynamically recruit specialized engineering `AgentTemplate`s and `AgentSet`s on demand.

## Seats (`AgentSet`)

| Seat | Replicas | `resetPolicy` | Role |
|---|---|---|---|
| `researcher` | 1 | `AfterAssignment` | Researches domain best practices, capability gaps, infrastructure trade-offs, and specialist roles |
| `bughunter` | 1 | `AfterAssignment` | Runs in parallel with `researcher` to hunt real bugs, races, edge cases, and DX/code polish debt so the org balances quality against feature delivery |
| `pm` | 1 | `Never` | Maintains long-horizon roadmap context, curates feature/bug/polish issues, and picks 1–3 parallel tracks |
| `architect` | 1 | `Never` | Makes architecture & infrastructure decisions, scopes non-overlapping `PathLease` globs, assigns teams, and emits `recruitingRequests` |
| `recruiter` | 1 | `AfterAssignment` | Researches requested specialist roles (e.g., data engineer, security expert, query optimizer) and provisions dedicated kagent `AgentTemplate`s, `Agent`s, and Slipway `AgentSet`s |

## Leadership Cycle (`WorkflowSchedule`)

```text
  research ──┐
             ├──▶ pm ──▶ architect ──▶ recruit
 bughunter ──┘
```

- Uses `mode: Continuous` with `carryForwardOutput: true` so the council sees prior cycle outcomes and active recruited teams automatically.
- Uses an immutable `schemaFrom` ConfigMap (`__TEAM_NAME__-schemas`) so every step's structured JSON contract is versioned once and validated by Slipway.
- Includes a native event-driven `WorkflowDispatch` (`dispatch.yaml`) that watches `WorkflowSchedule/__TEAM_NAME__-loop` completions and fans out `architect.workItems` into parallel `WorkflowBacklog`s routed to dynamically recruited specialist `AgentSet`s with active-key deduplication and concurrency bounds.

## Usage

```sh
NAMESPACE=kagent \
TEAM_NAME=acme-leadership \
MODEL_CONFIG=my-model \
TARGET_SCOPE=org/acme-leadership \
./scripts/render-team.sh teams/autonomous-org --apply
```
