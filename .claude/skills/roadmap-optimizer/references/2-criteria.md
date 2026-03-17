# 2. Success Criteria: What Makes a Good Roadmap

This document defines **what we're trying to achieve** with the optimization.

---

## The Core Trade-offs

Every migration roadmap involves balancing three competing goals:

```
                    ┌─────────────────┐
                    │   GO FASTER     │
                    │  (shorter time) │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              │              ▼
    ┌─────────────────┐      │    ┌─────────────────┐
    │   LESS DEBT     │◄─────┴───►│  BETTER TARGET  │
    │ (cleaner code)  │           │ (more strategic)│
    └─────────────────┘           └─────────────────┘
```

**You cannot maximize all three.** The optimizer helps you understand the trade-offs and choose.

---

## Combined Objective Function

The optimizer minimizes a weighted combination of all objectives:

```
Minimize: Z = α₁ × T_total + α₂ × C_total - α₃ × BusinessValue - α₄ × RiskMitigation - α₅ × Quality

Where:
  α₁ = 0.40  (time weight — primary)
  α₂ = 0.15  (cost weight — secondary)
  α₃ = 0.20  (business value weight)
  α₄ = 0.15  (risk mitigation weight)
  α₅ = 0.10  (quality weight)
```

### Primary Objective: Minimize Total Transition Duration

```
T_total = max{completion_wave(cluster_i)} for all i ∈ Clusters

Where:
  completion_wave(cluster_i) = start_wave(cluster_i) + duration(cluster_i, approach_i)
```

### Secondary Objective: Minimize Total Cost (Including Future Migration)

```
C_total = Σ total_cost(cluster_i) for all i ∈ Clusters

Where:
  total_cost(cluster_i) = current_cost(cluster_i) + future_migration_cost(cluster_i)
  current_cost(cluster_i) = Σ (role_hours(r, cluster_i) × role_rate(r)) for all r ∈ Roles

  future_migration_cost(cluster_i) = {
      438 hours × average_role_rate   IF approach = Bridge-from-Legacy AND cluster ∈ future_cores
      0                               OTHERWISE
  }
```

**Key insight**: Bridge-from-Legacy and Strategic both cost similar hours upfront, but for clusters targeting future core systems (defined in config.future_core_systems), Bridge-from-Legacy incurs an *additional* future migration cost — making Strategic the preferred choice when available.

### Tertiary Objectives (Weighted)

| Objective | Weight | Formula | Description |
|-----------|--------|---------|-------------|
| Business Value | 20% | `Σ value(cluster_i) × completion_week(cluster_i)^(-1)` | Weighted value delivered, prioritising earlier delivery of high-value clusters |
| Risk Mitigation | 15% | `Σ (1 - P_failure(cluster_i))` | Aggregated success probability across all clusters |
| Quality | 10% | `Σ reconciliation_pass_rate(cluster_i) / N_clusters` | Average data reconciliation pass rate |

---

## Primary Success Metrics

### 1. Total Duration (months)
- **What it measures**: How long until ALL packages are migrated
- **Good**: Under 48 months
- **Acceptable**: 48-60 months
- **Concerning**: Over 60 months

### 2. Strategic Coverage (%)
- **What it measures**: Percentage of effort using the Strategic migration approach
- **Good**: Over 60%
- **Acceptable**: 40-60%
- **Concerning**: Under 40%
- **Why it matters**: Strategic migrations align with the target architecture; non-strategic creates technical debt

### 3. Technical Debt Score
- **What it measures**: Accumulated "shortcuts" that will need fixing later
- **How it's calculated**:
  - Build-to-Legacy packages: +2 × complexity score
  - Bridge-to-Model packages: +1 × complexity score
  - Strategic packages: +0
- **Good**: Under 100
- **Acceptable**: 100-200
- **Concerning**: Over 200

### 4. Resource Utilization (%)
- **What it measures**: How efficiently team capacity is used
- **Good**: 70-85% (leaves room for surprises)
- **Acceptable**: 60-90%
- **Concerning**: Under 60% (wasted capacity) or over 90% (no slack)

---

## Secondary Success Metrics

### 5. Dependency Satisfaction
- **What it measures**: Are upstream packages always completed before downstream?
- **Target**: 100% (this is a hard constraint, not negotiable)

### 6. Domain Balance
- **What it measures**: Are business domains progressing in parallel?
- **Why it matters**: Stakeholders from each domain want to see progress
- **Good**: All domains show meaningful progress by month 12

### 7. Risk Distribution
- **What it measures**: Are high-risk packages spread out, not clustered?
- **Why it matters**: Clustered risk = clustered failures
- **Good**: No more than 3 high-risk packages active simultaneously

---

## How Scenarios Prioritize Differently

| Scenario | Duration Priority | Strategic Priority | Debt Priority |
|----------|------------------|-------------------|---------------|
| **Fast Exit** | 60% | 10% | 30% |
| **Balanced** | 30% | 40% | 30% |
| **Target-First** | 20% | 60% | 20% |

### Fast Exit
- Gets you off the legacy platform as quickly as possible
- Accepts higher technical debt
- Uses more Build-to-Legacy approaches
- **Choose this if**: Legacy licenses are expiring, or there's pressure to decommission the source system quickly

### Balanced
- Middle ground on all dimensions
- Moderate debt, moderate speed
- **Choose this if**: No extreme pressure either way, want a sensible default

### Target-First
- Maximizes strategic architecture alignment
- Willing to take longer to do it right
- Minimizes future rework
- **Choose this if**: Long-term architecture matters more than short-term speed

---

## Quality Checklist for Generated Roadmaps

Before presenting a roadmap to stakeholders, verify:

- [ ] **No constraint violations**: All hard constraints satisfied
- [ ] **Reasonable utilization**: Not over 90% in any month
- [ ] **Progressive completion**: Packages completing throughout, not all at the end
- [ ] **Domain coverage**: Each domain shows progress by month 12
- [ ] **Dependency respect**: No package starts before its dependencies finish
- [ ] **Mode appropriateness**: High-criticality packages prefer Strategic mode

---

## What "Success" Looks Like in Practice

**A good roadmap should:**

1. **Be believable** - Stakeholders look at it and say "yes, this could work"
2. **Show trade-offs clearly** - "If you want X, you give up Y"
3. **Respect reality** - Teams can't do more than capacity allows
4. **Enable decisions** - Gives leadership enough info to choose a path

**Red flags that indicate a problem:**

- ❌ All packages start in month 0 (ignoring dependencies)
- ❌ Team utilization over 100% for multiple months
- ❌ Strategic coverage is 0% or 100% (no nuance)
- ❌ Total duration equals horizon exactly (no slack)

---

## Quality Gates

Before any cluster goes live, it must pass these sequential gates:

```
Gate 1: Design Review
├── Architecture approved
├── Data model validated
└── Transformation logic signed off

Gate 2: Code Complete
├── All notebooks developed
├── Unit tests passing
└── Code review completed

Gate 3: Integration Test
├── End-to-end flow working
├── Performance benchmarks met
└── Error handling validated

Gate 4: Reconciliation
├── Row count variance <1%
├── Aggregate variance <0.5%
├── Business rule validation passed
└── SCD handling verified

Gate 5: Go-Live Ready
├── UAT signed off
├── Runbook approved
├── Rollback plan documented
└── Monitoring configured
```

---

## Escalation Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Schedule variance | >10% | >20% | Re-prioritisation meeting |
| Reconciliation variance | >1% | >5% | Root cause analysis |
| Resource utilisation | <70% or >95% | <60% or >100% | Rebalancing |
| Quality gate failures | 2 consecutive | 3+ consecutive | Process review |

---

## Utilisation Targets

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Team utilisation | 85% | 75-95% |
| Buffer for unplanned work | 15% | 10-25% |
| Sprint velocity variance | ±10% | ±15% max |

---

## POC Requirements

Before scaling any approach, validate with a Proof of Concept:

| Approach | POC Cluster | Success Criteria |
|----------|-------------|------------------|
| Strategic | 1 cluster from each domain | Full target model compliance, <2% variance |
| Bridge-to-Model | 1 cluster per analytical model | Successful SAS output mapping, functional reporting |
| Bridge-from-Legacy | 1 cluster | Dual-run stable, <1% variance for 5 cycles |

---

## Governance Cadence

| Frequency | Activity | Participants |
|-----------|----------|--------------|
| Weekly | Wave review, progress tracking | Technical leads, PMs |
| Bi-weekly | Score recalculation, priority adjustment | Data architects, business owners |
| Monthly | Roadmap review, resource rebalancing | Steering committee |
| Quarterly | Strategic re-prioritisation | Executive sponsors |

### Sign-off Matrix

| Deliverable | Technical Sign-off | Business Sign-off | Final Approval |
|-------------|-------------------|-------------------|----------------|
| Design | Data Architect | Domain SME | Tech Lead |
| Code | Sr Developer | — | Data Architect |
| Test Results | QA Lead | Business Analyst | Tech Lead |
| Go-Live | Tech Lead | Business Owner | Program Manager |
| Post-Cutover | Operations | Business Owner | Steering Committee |
