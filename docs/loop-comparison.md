# Full loop vs interview-mode loop

Companion to [multi-agent-setup.md](multi-agent-setup.md) and [multi-agent-diagrams.md](multi-agent-diagrams.md).

## 1. Full loop

```mermaid
flowchart TD
    A([Task]) --> CL{Classify mode}
    CL -->|A| MA[implementer → qa → 2 review passes → PR to dev]
    CL -->|B or C| P1[Pick ready tasks]
    P1 --> P2["Decompose<br/>up to 3 decomposers"]
    P2 --> P3{Contract change?}
    P3 -->|yes| ARCH[/Architecture stop: you decide/]
    P3 -->|no| P4[Cross-check plans]
    P4 -->|clash, up to 3 rounds| P2
    P4 --> P5["Plan review<br/>GPT-6 Sol"]
    P5 --> P6{Evals flag?}
    P6 -->|yes| EV["/eval-create with you"]
    P6 -->|no| B1
    EV --> B1["Build on task branch<br/>worktree in Mode B"]
    B1 --> B2[qa writes failing tests]
    B2 --> B3[implementer builds]
    B3 --> B4[qa runs tests]
    B4 --> B5{Evals flagged?}
    B5 -->|yes| B5a[eval-runner → checks → judge]
    B5 -->|no| B6
    B5a --> B6["Review: answers-ask, principles, alternatives<br/>GPT-6 Luna"]
    B6 --> B7{Decide}
    B7 -->|fail| B3
    B7 -->|plan wrong| P2
    B7 -->|architecture| ARCH
    B7 -->|pass| M1[Merge dev in, full suite]
    M1 --> M2[PR into dev, checks, merge]
    M2 --> M3[Final answers-ask over merged result]
    M3 -->|more tasks ready| P1
    M3 --> D([Promote dev to uat; you approve main])
    B7 -.->|3 rounds failed| H[/Stop, report/]
```

## 2. Interview-mode loop

```mermaid
flowchart TD
    A(["interview: task"]) --> S["Check dev is clean and up to date<br/>create feature branch"]
    S --> P1["One decomposer writes plan.md"]
    P1 --> P2{"Contract change?"}
    P2 -->|yes| ARCH[/Architecture stop: you decide/]
    P2 -->|no| P3[/"You read the plan<br/>and approve it"/]
    P3 --> B1[qa writes tests]
    B1 --> B1a{Fail for the right reason?}
    B1a -->|no| B1
    B1a -->|yes| B2[implementer builds]
    B2 --> B3[qa runs tests]
    B3 -->|fail| B2
    B3 --> R{"Codex signed in?"}
    R -->|yes| R1["answers-ask review<br/>GPT-6 Luna"]
    R -->|no| R2["Skip review and say so"]
    R1 --> R3{Verdict}
    R3 -->|"CHANGES, one fix round"| B2
    R3 -->|PASS| M1
    R2 --> M1
    M1["Commit, merge into dev<br/>local if no remote"] --> D([Done: show summary])
    R3 -.->|"still failing after the fix round"| H[/Stop, report/]
```

## What interview mode drops and keeps

| Dropped | Kept |
| --- | --- |
| Mode classification, cross-check, planner steps | Architecture stop rule |
| Evals, wild-card, calibration | You read and approve the plan |
| `principles` and `alternatives` passes, plan review (Sol) | Tests first, confirmed failing for the right reason |
| Up to 3 decomposers, 3 fix rounds | One `answers-ask` review pass, one fix round |
| Parallel worktrees | Branch flow: feature branch, merge into `dev` |
