# 8. Workflow & Orchestration: How to Execute This Skill

This document defines **exactly how Claude should execute** the roadmap optimization — step by step, including when to use subagents and how to parallelize work.

---

## Overview: The Full Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROADMAP OPTIMIZATION PIPELINE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 1: Data Ingestion          PHASE 2: Optimization    PHASE 3: Output │
│  ─────────────────────            ──────────────────────   ──────────────── │
│                                                                             │
│  ┌─────────────┐                  ┌─────────────┐          ┌─────────────┐ │
│  │ Load Jobs   │                  │ Run Solver  │          │ Generate    │ │
│  │ (parallel)  │───┐              │ (3 scenarios│───┐      │ Excel       │ │
│  └─────────────┘   │              │  parallel)  │   │      │ Report      │ │
│                    │              └─────────────┘   │      └─────────────┘ │
│  ┌─────────────┐   │                                │                      │
│  │ Validate    │───┼──► Packages ──────────────────►├──► Results ─────────►│
│  │ Data        │   │                                │                      │
│  └─────────────┘   │              ┌─────────────┐   │      ┌─────────────┐ │
│                    │              │ Calculate   │───┘      │ Present to  │ │
│  ┌─────────────┐   │              │ Metrics     │          │ User        │ │
│  │ Aggregate   │───┘              └─────────────┘          └─────────────┘ │
│  │ to Packages │                                                           │
│  └─────────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Ingestion & Preparation

### Step 1.1: Understand the User's Data

**Do this yourself (no subagent needed)**

1. Ask the user where their job data is located
2. Determine the format:
   - Directory of JSON files?
   - Single JSON array?
   - CSV/Excel that needs conversion?
3. Locate the configuration file (or help create one)

**Questions to ask if unclear:**
- "Where are your SAS job JSON files located?"
- "Do you have a configuration file, or should I use defaults?"
- "What's your team capacity (number of people)?"
- "What's your target timeline (months)?"

---

### Step 1.2: Load and Validate Job Data

**Spawn subagent: `data-loader`**

```
Task: Load and validate job data
─────────────────────────────────
Input:
  - Job data path: <user-provided path>
  - Expected format: JSON files / JSON array / CSV

Instructions:
  1. Read all job files from the specified location
  2. Validate each job against the schema (see references/schemas.md)
  3. Report:
     - Total jobs found
     - Jobs with missing required fields
     - Jobs with invalid domain values
     - Dependency integrity issues (references to non-existent jobs)
  4. Save validated jobs to: <workspace>/validated_jobs.json

Output:
  - validated_jobs.json (cleaned job data)
  - validation_report.md (issues found)
```

**Why a subagent?** Loading 29,000+ files can be slow and may require error handling. Isolating this allows the main agent to continue planning.

---

### Step 1.3: Build Dependency Graph & Aggregate Packages

**Spawn subagent: `package-aggregator`**

```
Task: Aggregate jobs into migration packages
────────────────────────────────────────────
Input:
  - Validated jobs: <workspace>/validated_jobs.json
  - Configuration: <config-path>

Instructions:
  1. Build dependency graph using networkx
  2. Identify strongly connected components
  3. Cluster jobs by domain and shared dependencies
  4. Create packages with calculated metrics:
     - total_effort_days
     - complexity_score
     - business_value
     - risk_score
     - upstream/downstream dependencies
  5. Target: 100-500 packages (adjust clustering if outside range)

Output:
  - packages.json (migration packages)
  - aggregation_report.md (clustering decisions, stats)
```

**Key metrics to report:**
- Number of packages created
- Package size distribution (min/max/avg jobs per package)
- Domain distribution
- Dependency graph density

---

## Phase 2: Optimization

### Step 2.1: Run Three Scenarios in Parallel

**Spawn 3 subagents simultaneously: `optimizer-fast-exit`, `optimizer-balanced`, `optimizer-target-first`**

```
Task: Run Fast Exit optimization
────────────────────────────────
Input:
  - Packages: <workspace>/packages.json
  - Configuration: <config-path>

Instructions:
  1. Load packages and configuration
  2. Set scenario weights:
     - minimize_duration: 0.6
     - maximize_strategic: 0.1
     - minimize_tech_debt: 0.3
  3. Build OR-Tools CP-SAT model (see references/7-mathematical-formulation.md)
  4. Solve with 5-minute timeout
  5. Extract solution and calculate metrics

Output:
  - fast_exit_result.json (schedule + metrics)
  - fast_exit_solver_log.txt (solver statistics)
```

```
Task: Run Balanced optimization
───────────────────────────────
[Same structure, different weights]
  - minimize_duration: 0.3
  - maximize_strategic: 0.4
  - minimize_tech_debt: 0.3

Output:
  - balanced_result.json
  - balanced_solver_log.txt
```

```
Task: Run Target-First optimization
───────────────────────────────────
[Same structure, different weights]
  - minimize_duration: 0.2
  - maximize_strategic: 0.6
  - minimize_tech_debt: 0.2

Output:
  - target_first_result.json
  - target_first_solver_log.txt
```

**Why parallel?** Each scenario is independent. Running them simultaneously reduces total time from ~15 minutes to ~5 minutes.

---

### Step 2.2: Validate and Compare Results

**Do this yourself (no subagent needed)**

Once all three optimizers complete:

1. Load all three result files
2. Verify no constraint violations
3. Create comparison table:

| Metric | Fast Exit | Balanced | Target-First |
|--------|-----------|----------|--------------|
| Duration (months) | ? | ? | ? |
| Strategic Coverage | ? | ? | ? |
| Technical Debt | ? | ? | ? |
| Build-to-Legacy % | ? | ? | ? |
| Bridge % | ? | ? | ? |
| Strategic % | ? | ? | ? |

4. Identify the "recommended" scenario based on user priorities

---

## Phase 3: Output Generation

### Step 3.1: Generate Excel Report

**Spawn subagent: `excel-generator`**

```
Task: Generate comprehensive Excel report
─────────────────────────────────────────
Input:
  - Packages: <workspace>/packages.json
  - Results:
    - <workspace>/fast_exit_result.json
    - <workspace>/balanced_result.json
    - <workspace>/target_first_result.json
  - Configuration: <config-path>

Instructions:
  1. Use scripts/excel_generator.py
  2. Generate all 12 sheets:
     - Assumptions (editable parameters, blue font inputs)
     - Package_Data (structured Excel Table)
     - Schedule_FastExit / Schedule_Balanced / Schedule_TargetFirst
     - Executive_Summary (formula-driven KPIs)
     - Scenario_Comparison (charts + formulas)
     - Timeline_Gantt (mode-coloured Gantt bars)
     - Effort_Cost_Model (cost projections using Assumptions!fte_daily_rate)
     - Risk_Assessment (weighted risk scoring model)
     - Dependency_Analysis (critical path detection)
     - Data_Appendix (configuration recap with formulas)
  3. Apply financial-model conventions: blue font = input, black = formula
  4. Include named ranges, Excel Tables, conditional formatting, charts

Output:
  - migration_roadmap_report.xlsx (12-sheet financial model)
```

---

### Step 3.2: Present Results to User

**Do this yourself (main agent)**

1. Summarize key findings:
   ```
   "I've completed the optimization. Here's what I found:

   📊 Analyzed: 127 packages from 29,551 jobs

   Three scenarios compared:
   • Fast Exit: 36 months, 28% strategic, high tech debt
   • Balanced: 42 months, 58% strategic, moderate debt  ← Recommended
   • Target-First: 54 months, 82% strategic, minimal debt

   The Excel report is saved at: <path>
   "
   ```

2. Ask if user wants:
   - Deeper analysis of any scenario
   - What-if analysis (different capacity, timeline)
   - Additional visualizations

---

## Subagent Summary Table

| Subagent | Phase | Parallelizable | Typical Duration | Key Output |
|----------|-------|----------------|------------------|------------|
| `data-loader` | 1 | No (first step) | 1-3 min | validated_jobs.json |
| `package-aggregator` | 1 | No (needs jobs) | 1-2 min | packages.json |
| `optimizer-fast-exit` | 2 | **Yes** (with other optimizers) | 2-5 min | fast_exit_result.json |
| `optimizer-balanced` | 2 | **Yes** | 2-5 min | balanced_result.json |
| `optimizer-target-first` | 2 | **Yes** | 2-5 min | target_first_result.json |
| `excel-generator` | 3 | No (needs all results) | 1-2 min | .xlsx report |

**Total time (sequential):** ~15-20 minutes
**Total time (with parallelization):** ~8-12 minutes

---

## Workspace Structure

Create this directory structure for intermediate files:

```
<workspace>/
├── input/
│   ├── jobs/                    # Original job JSON files (or symlink)
│   └── config.json              # Optimization configuration
├── intermediate/
│   ├── validated_jobs.json      # Cleaned job data
│   ├── validation_report.md     # Data quality issues
│   ├── packages.json            # Aggregated packages
│   └── aggregation_report.md    # Clustering decisions
├── results/
│   ├── fast_exit_result.json    # Scenario 1 output
│   ├── fast_exit_solver_log.txt
│   ├── balanced_result.json     # Scenario 2 output
│   ├── balanced_solver_log.txt
│   ├── target_first_result.json # Scenario 3 output
│   └── target_first_solver_log.txt
└── output/
    └── migration_roadmap_report.xlsx  # Final deliverable
```

---

## Error Handling

### If data loading fails:
1. Report specific errors (missing files, invalid JSON)
2. Ask user to fix and retry
3. Do NOT proceed to aggregation

### If optimization returns INFEASIBLE:
1. Report which constraints couldn't be satisfied
2. Suggest remediation:
   - Extend horizon
   - Increase capacity
   - Check for circular dependencies
3. Offer to re-run with relaxed constraints

### If optimization times out (UNKNOWN):
1. Report partial progress if available
2. Suggest:
   - Reduce problem size (more aggressive aggregation)
   - Increase timeout
   - Simplify constraints

### If Excel generation fails:
1. Ensure openpyxl is installed
2. Check for file permission issues
3. Fallback: generate CSV files instead

---

## What-If Analysis Workflow

When user asks "what if we had more capacity?" or "what if we extended timeline?":

**Spawn subagent: `what-if-analyzer`**

```
Task: Run what-if analysis
──────────────────────────
Input:
  - Packages: <workspace>/packages.json
  - Base configuration: <config-path>
  - Variation: { "team_capacity": 8 }  # or { "horizon": 72 }

Instructions:
  1. Create modified configuration
  2. Re-run Balanced scenario only (fastest feedback)
  3. Compare to baseline Balanced result
  4. Report delta:
     - Duration change: -X months
     - Strategic coverage change: +Y%
     - Resource utilization change: Z%

Output:
  - what_if_result.json
  - what_if_comparison.md
```

---

## Governance & Iteration Cadence

Once the initial roadmap is generated, the plan should be reviewed and refined on a regular cadence:

| Frequency | Activity | Participants |
|-----------|----------|--------------|
| Weekly | Wave review, progress tracking | Technical leads, PMs |
| Bi-weekly | Score recalculation, priority adjustment | Data architects, business owners |
| Monthly | Roadmap review, resource rebalancing | Steering committee |
| Quarterly | Strategic re-prioritisation | Executive sponsors |

### When to Re-run the Optimizer
- Team capacity changes (FTEs added or removed)
- System decommissioning date moves
- New clusters discovered or scope changes
- A POC reveals significantly different effort estimates
- Schedule variance exceeds 20% threshold

---

## Checklist: Before Starting Optimization

- [ ] Job data location confirmed
- [ ] Configuration file exists or defaults agreed
- [ ] Team capacity specified
- [ ] Migration horizon specified
- [ ] Domain priorities confirmed (or use defaults)
- [ ] User understands the three scenarios

## Checklist: Before Presenting Results

- [ ] All three scenarios completed successfully
- [ ] No constraint violations in any solution
- [ ] Excel report generated and accessible
- [ ] Comparison table prepared
- [ ] Recommendation ready with rationale
