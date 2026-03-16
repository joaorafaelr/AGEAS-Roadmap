---
name: roadmap-optimizer
description: Advanced roadmap optimization for large-scale system migration and modernization projects. Use this skill when users need to optimize migration schedules, analyze job dependencies, apply resource constraints, or generate strategic roadmaps with multiple execution approaches. Handles any type of migration project including data platform transitions (SAS-to-Databricks, Oracle-to-Snowflake), application modernization (mainframe to cloud), or complex system replacements. Generates comprehensive Excel workbooks with executive dashboards, Gantt timelines, and scenario comparisons. Trigger for migration planning, modernization roadmaps, multi-mode project scheduling, resource-constrained optimization, or when users mention system migration, platform transitions, complex project scheduling, or need beautiful Excel reports with migration analysis.
compatibility:
  tools:
    - Read
    - Write
    - Bash
    - Glob
    - Task
  packages:
    - ortools
    - pandas
    - networkx
    - matplotlib
    - seaborn
    - json
    - openpyxl
---

# Roadmap Optimizer

A skill for optimizing complex system migration and modernization roadmaps using constraint-based scheduling.

## What This Skill Does

Given a set of jobs, processes, or systems that need to migrate to a new platform, this skill:

1. **Aggregates** individual items into manageable migration packages
2. **Optimizes** the schedule using constraint programming (OR-Tools)
3. **Generates** multiple scenarios with different strategic approaches
4. **Produces** comprehensive Excel reports for stakeholders

## Common Use Cases

This skill excels at optimizing roadmaps for:

- **Data Platform Migrations**: SAS-to-Databricks, Oracle-to-Snowflake, Teradata-to-BigQuery
- **Application Modernization**: Mainframe to cloud, legacy systems to microservices
- **Technology Stack Migrations**: Database migrations, ETL modernization, BI platform transitions
- **Enterprise System Replacements**: ERP migrations, CRM modernization, core banking system transitions
- **Cloud Migrations**: On-premise to cloud, multi-cloud transitions

## Migration Approaches

The optimizer supports multiple execution strategies:

- **Direct/Strategic**: Migrate directly to the target state (cleanest but longest)
- **Bridge/Lift-and-Shift**: Create temporary bridge solutions (faster but with technical debt)
- **Legacy Replication**: Replicate current behavior then converge (safest but most expensive)

## Quick Start

**IMPORTANT**: Read `references/8-workflow-orchestration.md` first — it tells you exactly how to execute this skill step-by-step, including when to spawn subagents.

### High-Level Flow

```
Phase 1: Data Ingestion       Phase 2: Optimization      Phase 3: Output
────────────────────────      ─────────────────────      ───────────────
[Load Jobs]                   [Fast Exit    ]            [Generate Excel]
     ↓                        [Balanced     ] ← parallel [Present Results]
[Validate Data]               [Target-First ]
     ↓
[Aggregate Packages]
```

### Subagent Usage

| Task | Subagent | Run In Parallel? |
|------|----------|------------------|
| Load & validate jobs | `data-loader` | No (first step) |
| Aggregate packages | `package-aggregator` | No (needs jobs) |
| Run Fast Exit | `scenario-optimizer` | **Yes** |
| Run Balanced | `scenario-optimizer` | **Yes** |
| Run Target-First | `scenario-optimizer` | **Yes** |
| Generate Excel | `excel-generator` | No (needs all results) |

See `agents/` folder for exact subagent prompts.

---

## Reference Documentation

### Understanding the System
| File | What It Covers |
|------|----------------|
| `references/1-inputs.md` | Required data formats and input files |
| `references/2-criteria.md` | What makes a "good" roadmap - success metrics |
| `references/3-hard-constraints.md` | Rules that can NEVER be violated |
| `references/4-soft-constraints.md` | Preferences that CAN be traded off |
| `references/5-optimization.md` | How the solver works, objective weights |
| `references/6-outputs.md` | Excel report structure and deliverables |

### Technical Details
| File | What It Covers |
|------|----------------|
| `references/7-mathematical-formulation.md` | **Full math model**: variables, formulas, weights |
| `references/8-workflow-orchestration.md` | **Execution guide**: step-by-step, subagents, parallelization |
| `references/schemas.md` | Technical JSON schemas for all data |

### Subagent Prompts
| File | When To Use |
|------|-------------|
| `agents/data-loader.md` | Spawning job loading subagent |
| `agents/package-aggregator.md` | Spawning aggregation subagent |
| `agents/scenario-optimizer.md` | Spawning optimization subagents (×3) |
| `agents/excel-generator.md` | Spawning report generation subagent |

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/package_aggregator.py` | Groups jobs into migration packages |
| `scripts/mrcpsp_optimizer.py` | Runs the constraint solver |
| `scripts/excel_generator.py` | Creates the 12-sheet financial-model Excel report |
| `scripts/domain_data_processor.py` | Processes domain-specific cluster reports and similarity scores |
| `scripts/extract_similarity_scores.py` | Extracts similarity metrics from Excel files |

---

## Domain-Specific Features

The optimizer includes enhanced features for specific migration contexts:

### Data Platform Migrations
- **Lineage Analysis**: Understands upstream/downstream data dependencies
- **Volume-Based Sizing**: Estimates effort based on data volume and complexity
- **Analytical Model Integration**: Incorporates similarity scores for bridge approaches

### Application Modernization
- **Service Dependency Mapping**: Handles API and service dependencies
- **Technology Stack Compatibility**: Considers platform compatibility constraints
- **Risk Assessment**: Evaluates migration risk based on complexity indicators

### Configuration Adaptability
The skill adapts to your specific context through configuration:

| Configuration Area | What It Controls |
|-------------------|------------------|
| **Domain Structure** | Business domains, sub-systems, service boundaries |
| **Migration Modes** | Available approaches (direct, bridge, legacy replication) |
| **Resource Model** | Team structure, capacity, skill levels, hourly rates |
| **Constraints** | Dependencies, deadlines, platform limitations |
| **Success Criteria** | Optimization objectives, quality gates, risk tolerance |

---

## Example Usage Patterns

### Pattern 1: Large Data Platform Migration
```
"I have 29,000+ SAS programs that need to migrate to Databricks
over 3-5 years. We have 2 teams of 3 people. Can you optimize our
migration roadmap and generate an Excel report with all scenarios?"
```

### Pattern 2: Application Modernization
```
"We have 150 legacy COBOL programs to modernize to Java microservices.
Some can be rewritten, others need a bridge approach. What's the
optimal migration sequence given our 4-person team?"
```

### Pattern 3: Database Migration
```
"We're migrating from Oracle to PostgreSQL - 500+ stored procedures,
200 tables, complex dependencies. Need a roadmap that minimizes
business disruption over 18 months."
```

---

## Execution Checklist

Before starting:
- [ ] Job/system data location confirmed
- [ ] Configuration file exists (or use defaults)
- [ ] Team capacity specified
- [ ] Migration horizon specified
- [ ] Business constraints identified

During optimization:
- [ ] All three scenarios run in parallel
- [ ] Each returns OPTIMAL or FEASIBLE status
- [ ] No constraint violations

Before presenting:
- [ ] Excel report generated
- [ ] Comparison table prepared
- [ ] Recommendation ready

---

## Output Format

The skill generates:

1. **Executive Summary** (Markdown): High-level findings and recommendations
2. **Technical Analysis** (JSON): Detailed optimization results and metrics
3. **Migration Roadmap** (Excel): 12-sheet workbook with:
   - Executive dashboard
   - Timeline Gantt chart
   - Resource utilization
   - Risk analysis
   - Scenario comparison
   - Package details
   - Financial projections

## Advanced Features

- **Parallel Scenario Optimization**: Runs multiple strategies simultaneously
- **Constraint Validation**: Ensures all solutions are feasible
- **Sensitivity Analysis**: Shows impact of constraint changes
- **Risk Assessment**: Evaluates migration risks and mitigation strategies
- **Cost Modeling**: Projects effort, duration, and resource costs
