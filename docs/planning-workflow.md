# Planning workflow (`/planner`)

> **Historical spec.** This describes the first version of the workflow, copied into each project, with Modes A, B and C. The live rules are [CLAUDE.md](../CLAUDE.md) and [.claude/workflow/loop.md](../.claude/workflow/loop.md): the workflow lives only in this workspace root, the modes are Simple, Parallel and Sequential, commits are capped at 30 lines and reviewed one at a time, and each PR gets a full `pr` review.

Companion to [multi-agent-setup.md](multi-agent-setup.md) (sections 7.15 and 7.16). Files live in `.claude/runs/<task-id>/planner/`.

## 1. The six steps, with outputs and your checkpoints

```mermaid
flowchart TD
    START(["/planner task-id description"]) --> R{"planner/ folder exists?"}
    R -->|"yes: read progress.md"| RES["Resume at the next unfinished step<br/>never redo a finished step"]
    R -->|no| REQ["Write request.md verbatim"]
    REQ --> S1
    RES --> S1

    S1["Step 1: Research and user stories<br/>code, docs, web<br/>out: 01-research-and-stories.md"] --> C1[/"You read the file in full<br/>go on, change, or stop"/]
    C1 --> S2["Step 2: Alternatives<br/>at least 3, each with falsifiable claims<br/>out: 02-alternatives.md"]
    S2 --> C2[/"You read, then decide"/]
    C2 --> S3["Step 3: Test the claims<br/>real code, data and tests in spikes/<br/>held or falsified, plus rerun command<br/>out: 03-claim-tests.md"]
    S3 --> C3[/"You read, then decide"/]
    C3 --> S4["Step 4: New alternative<br/>keep what held, replace what failed<br/>out: 04-new-alternative.md"]
    S4 --> C4[/"You read, then decide"/]

    C4 --> S5a["Step 5a: Draft<br/>solution architecture, software architecture,<br/>a flow diagram per user story<br/>out: 05-solution-draft.md"]
    S5a --> REF{{"Refinement with you in the main session<br/>one question at a time<br/>architecture skill for contracts"}}
    REF -->|"each answer"| DEC["Append your decision to 05-decisions.md"]
    DEC --> REF
    REF -->|"you say refinement is done"| S5b["Step 5b: Finalize<br/>apply every decision, list what is undecided<br/>out: 05-solution.md"]
    S5b --> C5[/"You read in full"/]

    C5 --> S6["Step 6: PRD<br/>problem, solution, architecture, stories,<br/>story-to-architecture map, big tasks with dependencies<br/>out: 06-prd.md"]
    S6 --> C6[/"You read in full"/]
    C6 --> GO{"Start /build?"}
    GO -->|yes| BUILD(["/build task-id<br/>tasks decomposed just in time"])
    GO -->|no| STOP([Stop, resume later])

    S1 -.->|"after each step"| PROG[("progress.md<br/>step, file, time, summary")]
    S3 -.-> PROG
    S5b -.-> PROG
    S6 -.-> PROG
    S1 -.->|"needs an agreed architecture changed"| ARCH[/"ARCHITECTURE CHANGE file:<br/>architecture-change-planner.md<br/>you decide"/]
```

## 2. Who does what in each step

```mermaid
sequenceDiagram
    participant You
    participant Main as Main session (/planner command)
    participant Pl as planner subagent (Opus)
    Main->>Pl: step 1, task-id
    Pl-->>Main: 01 file + summary under 10 lines
    Main->>You: path to read in full, up to 5 lines on what to check
    You->>Main: go on, change, or stop
    Note over Main,Pl: same pattern for steps 2, 3, 4
    Main->>Pl: step 5 "draft"
    Pl-->>Main: 05-solution-draft.md
    loop until you say refinement is done
        Main->>You: one question (architecture, contracts, flow)
        You->>Main: answer
        Main-->>Main: append to 05-decisions.md
    end
    Main->>Pl: step 5 "finalize"
    Pl-->>Main: 05-solution.md
    Main->>Pl: step 6
    Pl-->>Main: 06-prd.md
    Main->>You: read the PRD, then start /build?
```

## 3. How it connects to the build

```mermaid
flowchart LR
    PRD["06-prd.md<br/>big tasks + dependencies"] --> BOARD["build-board.md<br/>all tasks waiting"]
    BOARD --> G[/"You approve the board"/]
    G --> READY["Mark ready: dependencies merged into dev"]
    READY --> DEC["Decompose ready tasks only<br/>up to 3 at a time"]
    DEC --> LOOP[["Build loop<br/>see loop-comparison.md"]]
    LOOP --> MERGE["Merged into dev"]
    MERGE --> READY
```

## Notes

- **Why a subagent can't do step 5 alone:** it can't talk to you, so the refinement runs in the main session. Only the planner writes step files; the main session writes only `05-decisions.md` and `progress.md`.
- **Crash safety:** every step's output is a file, and `progress.md` records the last finished step, so `/planner <task-id>` resumes where it stopped.
- **Interview mode:** the planner is cut entirely. Use it only for a large feature, not for a 90-minute task.
