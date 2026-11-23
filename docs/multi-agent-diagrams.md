# Multi-agent workflow: diagrams

> **Historical spec.** This describes the first version of the workflow, copied into each project, with Modes A, B and C. The live rules are [CLAUDE.md](../CLAUDE.md) and [.claude/workflow/loop.md](../.claude/workflow/loop.md): the workflow lives only in this workspace root, the modes are Simple, Parallel and Sequential, commits are capped at 30 lines and reviewed one at a time, and each PR gets a full `pr` review.

Companion to [multi-agent-setup.md](multi-agent-setup.md).

## 1. Roles and who calls whom

```mermaid
flowchart TD
    U([You]) <--> M["Main orchestrator<br/>(Opus, main session)"]
    M -->|"Mode A / Mode C: calls directly"| IMP[implementer<br/>Sonnet]
    M -->|"Mode A / Mode C"| QA[qa<br/>Sonnet]
    M -->|"up to 3 at a time"| DEC[decomposer<br/>Opus]
    M -->|"Mode B: one per checked plan"| WO[workflow-orchestrator<br/>Opus, own worktree]
    M -->|"/planner, one step per call"| PL[planner<br/>Opus]
    M -->|"/codex-ideas"| WC[wild-card<br/>Haiku wrapper → GPT-6 Sol]
    M -->|"loads for contract changes"| ARCH[[architecture skill]]
    M --> CR[codex-reviewer<br/>Haiku wrapper]
    WO --> IMP
    WO --> QA
    WO --> CR
    WO --> ER[eval-runner<br/>Sonnet]
    WO --> EJ[eval-judge<br/>Haiku wrapper → GPT-6 Luna]
    CR -->|plan| SOL[GPT-6 Sol]
    CR -->|answers-ask, principles, alternatives| LUNA[GPT-6 Luna]
```

## 2. Routing: which mode?

```mermaid
flowchart TD
    A([New task]) --> O{"Prefix override?<br/>simple: / parallel: / sequential:"}
    O -->|yes| FORCE[Use that mode]
    O -->|no| C1{"1–2 files, no contract change,<br/>easy to test, no LLM behaviour change?"}
    C1 -->|yes| MA["Mode A: Simple"]
    C1 -->|no| C2{"Dependencies between pieces,<br/>architecture/contract change,<br/>or you want to watch?"}
    C2 -->|yes| MC["Mode C: sequential / sensitive<br/>main session builds, one task at a time"]
    C2 -->|no| MB["Mode B: parallel<br/>one workflow-orchestrator per task"]
    FORCE --> MA & MB & MC
    MA --> A1["implementer → qa → answers-ask + principles → PR to dev"]
    MB --> LOOP
    MC --> LOOP
    LOOP[[Build loop, see diagram 3]]
```

## 3. The build loop

```mermaid
flowchart TD
    subgraph PLAN["Plan: main orchestrator, every task"]
        P1[Pick ready tasks<br/>deps merged into dev] --> P2[Decompose<br/>≤3 decomposers → plan.md]
        P2 --> P3{"Contract change or<br/>ARCHITECTURE CHANGE file?"}
        P3 -->|yes| STOP[/Architecture stop rule:<br/>show you, wait for decision/]
        P3 -->|no| P4[Cross-check plans<br/>→ cross-check.md]
        P4 --> P4b{Clash?}
        P4b -->|"yes, ≤3 rounds"| P2
        P4b -->|no| P5["codex-reviewer: plan pass<br/>(GPT-6 Sol)"]
        P5 --> P6{"Evals flag = yes?"}
        P6 -->|yes| EV["/eval-create with you"]
        P6 -->|no| READY
        EV --> READY([Checked plan])
    end
    READY --> B1
    subgraph BUILD["Build: workflow-orchestrator (B) or main session (C)"]
        B1[Set up on task branch<br/>from dev tip] --> B2[qa writes failing tests]
        B2 --> B3[implementer builds subtasks]
        B3 --> B4[qa runs tests]
        B4 --> B5["Evals if flagged:<br/>eval-runner → eval_checks.py → eval-judge"]
        B5 --> B6["Final review:<br/>answers-ask → principles → alternatives"]
        B6 --> B7{Decide}
        B7 -->|"tests/evals/review fail"| B3
        B7 -->|"plan wrong"| REPLAN[STATUS: REPLAN] --> P2
        B7 -->|"needs architecture change"| STOP
        B7 -->|"all pass"| DONE[Commit on branch]
    end
    B7 -.->|"3 rounds without success"| HALT[/Stop, report blocker/]
    DONE --> MG
    subgraph MERGE["Merge: main orchestrator, one branch at a time"]
        MG[Merge latest dev into branch] --> M2[qa runs full suite]
        M2 --> M3[PR into dev, checks, merge --merge]
        M3 --> M4[Remove worktree, update board]
        M4 --> M5["All tasks merged → answers-ask over merged result"]
    end
    M5 -->|"newly ready tasks"| P1
```

## 4. Planner and `/build` (new product or large feature)

```mermaid
flowchart LR
    S1["1 Research +<br/>user stories"] --> S2["2 Alternatives<br/>+ falsifiable claims"]
    S2 --> S3["3 Test claims<br/>with real code"]
    S3 --> S4["4 New alternative<br/>from what failed"]
    S4 --> S5a["5 Draft solution<br/>+ flow diagrams"]
    S5a --> S5b["Refine with you<br/>05-decisions.md"]
    S5b --> S5c["5 Finalize<br/>05-solution.md"]
    S5c --> S6["6 PRD<br/>06-prd.md"]
    S6 --> BUILD["/build: board of tasks<br/>+ dependencies"]
    BUILD --> LOOP[[Build loop, JIT decomposition]]
    S1 -.->|"you approve each step;<br/>progress.md allows resume"| S2
```

## 5. Evals

```mermaid
sequenceDiagram
    participant You
    participant Main as Main session (Opus)
    participant Runner as eval-runner (Sonnet)
    participant H as harness (project code)
    participant Checks as eval_checks.py
    participant Judge as eval-judge (GPT-6 Luna)
    You->>Main: /eval-create task-id
    Main->>You: draft case, review together
    Main-->>Main: save evals/<case>.yaml
    loop each case
        Runner->>H: python3 -m harness --message ...
        H-->>Runner: visible reply only
        H-->>H: append trace.jsonl
        Runner-->>Runner: write transcript.md
        Checks->>Checks: budgets, redundant calls → checks.json
        Judge->>Judge: score 4 dimensions → scores.json
    end
    Note over Main: Case passes only if all code checks pass<br/>and each dimension ≥ threshold
```

## 6. GitHub branching strategy

```mermaid
gitGraph
    commit id: "init"
    branch uat
    branch dev
    checkout dev
    branch feature/task-a
    commit id: "tests"
    commit id: "impl"
    checkout dev
    branch bugfix/task-b
    commit id: "fix"
    checkout dev
    merge feature/task-a id: "PR + checks"
    merge bugfix/task-b id: "PR + checks "
    checkout uat
    merge dev id: "promote to UAT"
    checkout main
    merge uat id: "release (YOU approve)" tag: "prod"
    checkout main
    branch hotfix/urgent
    commit id: "patch"
    checkout uat
    merge hotfix/urgent id: "hotfix → uat"
    checkout dev
    merge hotfix/urgent id: "hotfix → dev"
```

### Allowed PR directions (enforced by `branch-order` CI)

```mermaid
flowchart LR
    F["feature/* · bugfix/*"] -->|"PR, agents may merge"| DEV[dev<br/>env: dev]
    H["hotfix/*"] -->|PR| DEV
    H -->|PR| UAT[uat<br/>env: UAT]
    DEV -->|"PR, agents may merge"| UAT
    UAT -->|"PR, ONLY YOU approve + merge"| MAIN[main<br/>env: production]
    X["anything else / forks"] -.->|"blocked by CI"| MAIN
    style MAIN fill:#f8d7da,stroke:#b02a37
```

### Per-task git lifecycle

```mermaid
flowchart TD
    A["Main checkout on dev:<br/>clean? git pull --ff-only"] -->|dirty| ASK[/Stop and ask you/]
    A -->|clean| B[Record launch hash = dev tip]
    B --> C["Create feature/task-id<br/>(worktree in Mode B)"]
    C --> D[Commit work on branch]
    D --> E[Merge latest dev into branch<br/>resolve conflicts]
    E --> F[qa: full suite]
    F --> G["gh pr create --base dev"]
    G --> H["gh pr checks --watch"]
    H -->|green| I["gh pr merge --merge<br/>(no squash/rebase)"]
    H -->|red| D
    I --> J[Remove worktree, pull dev]
```
