# 7. Mathematical Formulation: The Complete Model

This document provides the **exact mathematical specification** of the optimization model - all variables, constraints, and objective function formulas.

---

## Problem Definition

**Type**: Multi-Mode Resource-Constrained Project Scheduling Problem (MRCPSP)

**Goal**: Schedule N packages across T time periods, choosing a migration mode for each, while respecting dependencies and resource limits, optimizing for duration/strategic coverage/technical debt.

---

## Sets and Indices

| Symbol | Description | Example |
|--------|-------------|---------|
| $P$ | Set of all packages | {pkg_1, pkg_2, ..., pkg_N} |
| $M$ | Set of migration modes | {build_to_legacy, bridge_to_model, strategic} |
| $T$ | Set of time periods (months) | {0, 1, 2, ..., horizon} |
| $i, j$ | Package indices | $i \in P$ |
| $m$ | Mode index | $m \in M$ |
| $t$ | Time period index | $t \in T$ |

---

## Parameters (Inputs)

### Package Parameters

| Symbol | Description | Source |
|--------|-------------|--------|
| $effort_i$ | Base effort in days for package $i$ | `package.total_effort_days` |
| $complexity_i$ | Complexity score for package $i$ | `package.complexity_score` |
| $value_i$ | Business value of package $i$ | `package.business_value` |
| $risk_i$ | Risk score of package $i$ | `package.risk_score` |
| $upstream_i$ | Set of packages that $i$ depends on | Derived from job dependencies |

### Mode Parameters

| Symbol | Mode | Value | Meaning |
|--------|------|-------|---------|
| $\mu_m$ | Duration multiplier | | |
| | build_to_legacy | 0.8 | 20% faster than baseline |
| | bridge_to_model | 1.0 | Baseline duration |
| | strategic | 1.3 | 30% slower than baseline |
| $\delta_m$ | Tech debt penalty | | |
| | build_to_legacy | 2.0 | Double debt accumulation |
| | bridge_to_model | 1.0 | Baseline debt |
| | strategic | 0.0 | No debt |
| $\eta_m$ | Resource efficiency | | |
| | build_to_legacy | 1.0 | Baseline efficiency |
| | bridge_to_model | 0.9 | 10% less efficient |
| | strategic | 0.8 | 20% less efficient |

### Cost Parameters

| Symbol | Mode | Hours | Description |
|--------|------|-------|-------------|
| $b_m$ | Base cost | | |
| | build_to_legacy | 438 | Same complexity as Strategic |
| | bridge_to_model | 150 | Minimal transformation, reuses SAS output |
| | strategic | 438 | Full target model redesign |
| $f_i$ | Future migration cost | 0 or 438 | Applies only to Bridge-from-Legacy on future cores |

### Global Parameters

| Symbol | Description | Default |
|--------|-------------|---------|
| $H$ | Planning horizon (months) | 60 |
| $C$ | Team capacity (people) | 6 |
| $C_{strategic}$ | Max concurrent Strategic clusters | 2 |
| $C_{total}$ | Max concurrent total clusters | 4 |
| $W$ | Weekly hours budget | 240 (6 FTEs × 40 hrs) |

### Future Core Systems

| System | Domain | Clusters Affected |
|--------|--------|------------------|
| Polaris | Policies | Policy-related clusters |
| DC Claims | Claims | Claims-related clusters |
| EDM | Entities | Entity-related clusters |

---

## Decision Variables

### Primary Variables

| Variable | Type | Domain | Meaning |
|----------|------|--------|---------|
| $x_{i,m}$ | Binary | {0, 1} | 1 if package $i$ uses mode $m$ |
| $start_i$ | Integer | [0, H] | Start month for package $i$ |
| $end_i$ | Integer | [1, H] | End month for package $i$ |

### Derived Variables

| Variable | Formula | Meaning |
|----------|---------|---------|
| $duration_{i,m}$ | $\lceil \frac{effort_i \times \mu_m \times complexity_i}{20} \rceil$ | Duration in months if using mode $m$ |
| $active_{i,t}$ | $(start_i \leq t) \land (end_i > t)$ | 1 if package $i$ is active in month $t$ |
| $resource_{i,m}$ | See formula below | People needed for package $i$ in mode $m$ |

### Resource Demand Formula

```
resource_demand(package_i, mode_m) =
    1  if complexity_i ≤ 2.0
    2  if 2.0 < complexity_i ≤ 4.0
    3  if complexity_i > 4.0
```

---

## Constraints

### C1: Mode Selection (exactly one mode per package)

$$\sum_{m \in M} x_{i,m} = 1 \quad \forall i \in P$$

**In code:**
```python
for package in packages:
    model.Add(sum(mode_vars[package][m] for m in modes) == 1)
```

### C2: Duration Linking (end = start + duration based on mode)

$$end_i = start_i + \sum_{m \in M} (duration_{i,m} \times x_{i,m}) \quad \forall i \in P$$

**In code:**
```python
for package in packages:
    for mode in modes:
        duration = get_mode_duration(package, mode)
        model.Add(end_vars[package] == start_vars[package] + duration).OnlyEnforceIf(mode_vars[package][mode])
```

### C3: Precedence (dependencies must complete first)

$$start_j \geq end_i \quad \forall i \in upstream_j, \forall j \in P$$

**In code:**
```python
for package_j in packages:
    for upstream_package_i in get_upstream_packages(package_j):
        model.Add(start_vars[package_j] >= end_vars[upstream_package_i])
```

### C4: Resource Capacity (don't exceed team size)

$$\sum_{i \in P} \sum_{m \in M} (resource_{i,m} \times x_{i,m} \times active_{i,t}) \leq C \quad \forall t \in T$$

**In code:**
```python
for month in range(horizon):
    month_demand = []
    for package in packages:
        for mode in modes:
            is_active = model.NewBoolVar(f'active_{package}_{mode}_{month}')
            # is_active = 1 iff (start <= month < end) AND mode is selected
            model.Add(start_vars[package] <= month).OnlyEnforceIf(is_active)
            model.Add(end_vars[package] > month).OnlyEnforceIf(is_active)
            model.Add(mode_vars[package][mode] == 1).OnlyEnforceIf(is_active)

            demand = get_resource_demand(package, mode)
            month_demand.append(demand * is_active)

    model.Add(sum(month_demand) <= team_capacity)
```

### C5: Timeline Boundary (all work within horizon)

$$end_i \leq H \quad \forall i \in P$$

**In code:**
```python
for package in packages:
    model.Add(end_vars[package] <= horizon)
```

### C6: Concurrent Strategic Limit

$$|\{i \in P : x_{i,strategic} = 1 \land active_{i,t} = 1\}| \leq C_{strategic} \quad \forall t \in T$$

**In code:**
```python
for month in range(horizon):
    strategic_active = []
    for pkg in packages:
        is_strategic_and_active = model.NewBoolVar(...)
        # is_strategic_and_active iff Strategic selected AND active in month
        strategic_active.append(is_strategic_and_active)
    model.Add(sum(strategic_active) <= 2)  # C_strategic = 2
```

### C7: Total Concurrent Cluster Limit

$$|\{i \in P : active_{i,t} = 1\}| \leq C_{total} \quad \forall t \in T$$

**In code:**
```python
for month in range(horizon):
    total_active = []
    for pkg in packages:
        is_active = model.NewBoolVar(...)
        total_active.append(is_active)
    model.Add(sum(total_active) <= 4)  # C_total = 4
```

### C8: System Decommissioning Deadlines

$$end_i \leq deadline(system(i)) \quad \forall i \in P \text{ where } system(i) \text{ has a deadline}$$

| System | Deadline Month |
|--------|---------------|
| CCS (Claims) | ~18 (Q3 2026) |
| DC Policy | ~30 (Q2 2027) |
| Tecnisys / Cogen | ~42 (Q3 2028) |

### C9: Strategic Approach Prerequisites

$$x_{i,strategic} = 1 \implies future\_core\_available(i) = 1 \quad \forall i \in P$$

Only clusters belonging to future cores (Polaris, DC Claims, EDM) can select Strategic mode.

---

## Objective Function

The objective is to **minimize** a weighted combination:

$$\text{minimize} \quad Z = w_1 \cdot Z_{duration} + w_2 \cdot Z_{strategic} + w_3 \cdot Z_{debt}$$

### Full 5-Component Formulation (from Ground Rules)

The complete objective combines five factors:

$$Z = \alpha_1 \cdot T_{total} + \alpha_2 \cdot C_{total} - \alpha_3 \cdot BV - \alpha_4 \cdot RM - \alpha_5 \cdot Q$$

| Weight | Default | Component |
|--------|---------|-----------|
| $\alpha_1$ | 0.40 | Time (primary — minimize total duration) |
| $\alpha_2$ | 0.15 | Cost (including future migration costs for Bridge-from-Legacy on future cores) |
| $\alpha_3$ | 0.20 | Business Value (maximise; earlier delivery of high-value clusters) |
| $\alpha_4$ | 0.15 | Risk Mitigation (maximise aggregated success probability) |
| $\alpha_5$ | 0.10 | Quality (average reconciliation pass rate) |

In the solver implementation, this is simplified to the three dominant dimensions (Duration, Strategic, Debt) since Business Value is folded into the Strategic term and Risk/Quality are handled via constraint penalties.

### Component 1: Duration (minimize)

$$Z_{duration} = \max_{i \in P}(end_i)$$

**In code:**
```python
max_end = model.NewIntVar(0, horizon, 'max_end')
model.AddMaxEquality(max_end, [end_vars[p] for p in packages])
duration_term = weights['minimize_duration'] * max_end
```

### Component 2: Strategic Coverage (maximize → negate to minimize)

$$Z_{strategic} = -\sum_{i \in P} (value_i \times 100 \times x_{i,strategic})$$

**In code:**
```python
strategic_term = 0
for package in packages:
    business_value = int(package['business_value'] * 100)
    strategic_term -= weights['maximize_strategic'] * business_value * mode_vars[package]['strategic']
```

### Component 3: Technical Debt (minimize)

$$Z_{debt} = \sum_{i \in P} \sum_{m \in M} (complexity_i \times \delta_m \times x_{i,m})$$

Expanded:
$$Z_{debt} = \sum_{i \in P} (complexity_i \times 2 \times x_{i,btl} + complexity_i \times 1 \times x_{i,btm} + 0)$$

**In code:**
```python
debt_term = 0
for package in packages:
    complexity = package['complexity_score']
    debt_term += weights['minimize_tech_debt'] * (
        complexity * 2 * mode_vars[package]['build_to_legacy'] +
        complexity * 1 * mode_vars[package]['bridge_to_model']
        # strategic contributes 0
    )
```

### Combined Objective

**In code:**
```python
model.Minimize(duration_term + strategic_term + debt_term)
```

### Component 4: Cost (Including Future Migration) — Optional Enhancement

$$Z_{cost} = \sum_{i \in P} (b_{m_i} \times complexity_i + f_i)$$

Where:
- $b_{m_i}$ = base cost of the selected approach (438h for Strategic/BfL, 150h for BtM)
- $f_i$ = 438 hours if Bridge-from-Legacy AND cluster belongs to future core, else 0

```
future_migration_cost(cluster_i) = {
    438 hours  IF approach(i) = Bridge-from-Legacy AND i ∈ {Polaris, DC_Claims, EDM clusters}
    0 hours    OTHERWISE
}
```

**Key insight**: For future core systems, Strategic and Bridge-from-Legacy cost the same upfront (438h), but Bridge-from-Legacy incurs an additional 438h later. The cost term incentivises Strategic for these clusters.

---

## Scenario Weight Configurations

### Fast Exit
| Weight | Value | Effect |
|--------|-------|--------|
| $w_1$ (duration) | 0.6 | Heavily minimize timeline |
| $w_2$ (strategic) | 0.1 | Mostly ignore strategic |
| $w_3$ (debt) | 0.3 | Some debt consideration |

### Balanced
| Weight | Value | Effect |
|--------|-------|--------|
| $w_1$ (duration) | 0.3 | Moderate timeline pressure |
| $w_2$ (strategic) | 0.4 | Primary focus on strategic |
| $w_3$ (debt) | 0.3 | Equal debt consideration |

### Target-First
| Weight | Value | Effect |
|--------|-------|--------|
| $w_1$ (duration) | 0.2 | Less timeline pressure |
| $w_2$ (strategic) | 0.6 | Strong strategic preference |
| $w_3$ (debt) | 0.2 | Lower debt focus |

---

## Worked Example

### Setup
- 3 packages: A, B, C
- B depends on A
- Horizon: 12 months
- Capacity: 3 people

### Package Data
| Package | Effort (days) | Complexity | Business Value |
|---------|---------------|------------|----------------|
| A | 40 | 2.0 | 0.8 |
| B | 60 | 3.0 | 0.9 |
| C | 30 | 1.5 | 0.5 |

### Duration Calculations
For package A (effort=40, complexity=2.0):
| Mode | Multiplier | Duration Formula | Result |
|------|------------|------------------|--------|
| build_to_legacy | 0.8 | ⌈(40 × 0.8 × 2.0) / 20⌉ | 4 months |
| bridge_to_model | 1.0 | ⌈(40 × 1.0 × 2.0) / 20⌉ | 4 months |
| strategic | 1.3 | ⌈(40 × 1.3 × 2.0) / 20⌉ | 6 months |

### Feasible Solution (Balanced weights)
| Package | Mode | Start | End | Duration |
|---------|------|-------|-----|----------|
| A | strategic | 0 | 6 | 6 |
| B | bridge_to_model | 6 | 12 | 6 |
| C | strategic | 0 | 4 | 4 |

### Objective Calculation
```
Duration term:    0.3 × 12 = 3.6
Strategic term:  -0.4 × (0.8×100×1 + 0.9×100×0 + 0.5×100×1) = -0.4 × 130 = -52
Debt term:        0.3 × (2.0×0×1 + 3.0×1×1 + 1.5×0×1) = 0.3 × 3.0 = 0.9

Total Z = 3.6 - 52 + 0.9 = -47.5
```

(Lower is better; negative because strategic term dominates)

---

## Variable Count and Complexity

For a problem with:
- N = 100 packages
- M = 3 modes
- H = 60 months

| Variable Type | Count | Formula |
|---------------|-------|---------|
| Mode selection ($x_{i,m}$) | 300 | N × M |
| Start times ($start_i$) | 100 | N |
| End times ($end_i$) | 100 | N |
| Activity indicators ($active_{i,t}$) | 6,000 | N × H |
| **Total binary/integer vars** | ~6,500 | |

| Constraint Type | Count | Formula |
|-----------------|-------|---------|
| Mode selection | 100 | N |
| Duration linking | 300 | N × M |
| Precedence | ~200 | Depends on dependencies |
| Resource capacity | 60 | H |
| Timeline boundary | 100 | N |
| Concurrent Strategic limit | 60 | H |
| Total concurrent limit | 60 | H |
| System deadlines | ~20 | Varies by domain |
| Strategic prerequisites | ~50 | Future core clusters |
| **Total constraints** | ~950 | |

**Solve time**: Typically 30-120 seconds for 100 packages.

---

## Solver Configuration

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 300      # 5 minute timeout
solver.parameters.num_search_workers = 8         # Parallel search
solver.parameters.log_search_progress = True     # Progress logging
```

### Status Codes
| Code | Meaning | Action |
|------|---------|--------|
| OPTIMAL | Best possible solution found | Use it |
| FEASIBLE | Valid solution, may not be best | Use it (good enough) |
| INFEASIBLE | No valid solution exists | Check constraints |
| UNKNOWN | Timed out without solution | Increase time or simplify |

---

## Sensitivity Analysis

To understand how robust a solution is:

### Duration Sensitivity
- If $w_1$ increases by 0.1: duration typically decreases 5-10%, strategic coverage drops 10-15%

### Capacity Sensitivity
- If $C$ increases from 6 to 8: duration typically decreases 15-25%
- If $C$ decreases from 6 to 4: duration may increase 30-50% or become infeasible

### Mode Multiplier Sensitivity
- If strategic multiplier decreases from 1.3 to 1.1: strategic coverage increases ~20%
