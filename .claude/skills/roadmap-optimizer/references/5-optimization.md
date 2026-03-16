# 5. Optimization: How the Solver Works

This document explains **how the optimizer calculates the best roadmap** using constraint programming.

---

## The Big Picture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   INPUTS     │     │   SOLVER     │     │   OUTPUTS    │
│              │     │              │     │              │
│ • Packages   │ ──► │ • Variables  │ ──► │ • Schedule   │
│ • Config     │     │ • Constraints│     │ • Metrics    │
│ • Weights    │     │ • Objective  │     │ • Trade-offs │
└──────────────┘     └──────────────┘     └──────────────┘
```

The optimizer uses **Google OR-Tools CP-SAT** - a constraint programming solver that:
1. Defines variables for every decision
2. Adds constraints that limit valid solutions
3. Minimizes/maximizes an objective function
4. Searches for the best valid solution

---

## Decision Variables

For each package `i`, the solver creates these variables:

### Timing Variables
| Variable | Type | Meaning |
|----------|------|---------|
| `start[i]` | Integer 0..horizon | Month when package starts |
| `end[i]` | Integer 1..horizon | Month when package ends |

### Mode Variables
| Variable | Type | Meaning |
|----------|------|---------|
| `mode[i, "build_to_legacy"]` | Boolean | 1 if using Build-to-Legacy |
| `mode[i, "bridge_to_model"]` | Boolean | 1 if using Bridge-to-Model |
| `mode[i, "strategic"]` | Boolean | 1 if using Strategic |

**Constraint**: Exactly one mode per package
```python
sum(mode[i, m] for m in modes) == 1
```

---

## Duration Calculation

Duration depends on the mode selected:

```python
base_effort = package.total_effort_days
complexity = package.complexity_score

mode_multipliers = {
    'build_to_legacy': 0.8,   # Fastest
    'bridge_to_model': 1.0,   # Baseline
    'strategic': 1.3          # Slowest
}

duration_months = ceil((base_effort × multiplier × complexity) / 20)
```

**Example**:
- Package with 40 effort days, complexity 2.0
- Build-to-Legacy: `(40 × 0.8 × 2.0) / 20 = 3.2` → 4 months
- Bridge-to-Model: `(40 × 1.0 × 2.0) / 20 = 4.0` → 4 months
- Strategic: `(40 × 1.3 × 2.0) / 20 = 5.2` → 6 months

---

## The Objective Function

The solver **minimizes** a weighted combination of objectives:

```
Objective = w₁ × Duration + w₂ × (-Strategic) + w₃ × TechDebt
```

### Full 5-Component Formulation

The complete objective function from the ground rules:

```
Minimize: Z = α₁ × T_total + α₂ × C_total - α₃ × BusinessValue - α₄ × RiskMitigation - α₅ × Quality

Where:
  α₁ = 0.40  (time weight — primary)
  α₂ = 0.15  (cost weight — including future migration costs)
  α₃ = 0.20  (business value weight — earlier delivery of high-value clusters)
  α₄ = 0.15  (risk mitigation weight — aggregated success probability)
  α₅ = 0.10  (quality weight — reconciliation pass rate)
```

In practice, the solver simplifies this to the three dominant components:

### Component 1: Duration
```python
# Minimize the latest end month
max_end = max(end[i] for all packages i)
duration_term = weight_duration × max_end
```

### Component 2: Strategic Coverage (negative because we maximize)
```python
# Maximize strategic usage, weighted by business value
strategic_term = -weight_strategic × sum(
    business_value[i] × 100 × mode[i, "strategic"]
    for all packages i
)
```

### Component 3: Technical Debt
```python
# Minimize accumulated debt
tech_debt_term = weight_debt × sum(
    complexity[i] × 2 × mode[i, "build_to_legacy"] +
    complexity[i] × 1 × mode[i, "bridge_to_model"]
    for all packages i
)
```

---

## Scenario Weights

Each scenario uses different weights:

### Fast Exit
```python
weights = {
    'minimize_duration': 0.6,    # Primary goal
    'maximize_strategic': 0.1,   # Not important
    'minimize_tech_debt': 0.3    # Secondary goal
}
```
**Result**: Aggressive timeline, accepts debt

### Balanced
```python
weights = {
    'minimize_duration': 0.3,    # Important but not dominant
    'maximize_strategic': 0.4,   # Primary goal
    'minimize_tech_debt': 0.3    # Equal to duration
}
```
**Result**: Middle ground on all dimensions

### Target-First
```python
weights = {
    'minimize_duration': 0.2,    # Less important
    'maximize_strategic': 0.6,   # Dominant goal
    'minimize_tech_debt': 0.2    # Secondary
}
```
**Result**: Maximizes strategic, accepts longer timeline

---

## How the Solver Searches

1. **Start with a random valid solution** (or fail if none exists)
2. **Iteratively improve** by trying small changes:
   - Change a package's start time
   - Switch a package's mode
   - Reorder dependent packages
3. **Accept changes that improve the objective**
4. **Stop when** no improvement found for N iterations, or time limit reached

### Solver Parameters
```python
solver.parameters.max_time_in_seconds = 300  # 5 minute timeout
```

---

## Resource Constraint Implementation

The solver tracks resource usage at each time point:

```python
for month in range(horizon):
    month_demand = []

    for package in packages:
        # Is this package active in this month?
        is_active = (start[package] <= month) AND (end[package] > month)

        if is_active:
            demand = resource_demand(package, selected_mode)
            month_demand.append(demand)

    # Constraint: total demand <= capacity
    sum(month_demand) <= team_capacity
```

### Concurrent Execution Limits

Beyond total capacity, specific concurrency constraints apply:

```python
for month in range(horizon):
    # At most 2 Strategic clusters in parallel (requires architect focus)
    strategic_active = sum(
        is_active[pkg][month] * mode_vars[pkg]['strategic']
        for pkg in packages
    )
    model.Add(strategic_active <= 2)

    # At most 4 total clusters in-flight (avoid context-switching overhead)
    total_active = sum(is_active[pkg][month] for pkg in packages)
    model.Add(total_active <= 4)
```

### Cost Awareness in Scheduling

The optimizer is aware that approach selection affects total cost:

| Approach | Current Cost | Future Migration Cost (for future cores) | Total |
|----------|-------------|----------------------------------------|-------|
| Strategic | 438 hours | €0 | 438 hours |
| Bridge-from-Legacy | 438 hours | +438 hours | **876 hours** |
| Bridge-to-Model | 150 hours | €0 | 150 hours |

This means for future core systems (Polaris, DC Claims, EDM), Bridge-from-Legacy effectively costs twice as much as Strategic. The solver factors this into the cost component of the objective function.

---

## Dependency Constraint Implementation

For every package pair where B depends on A:

```python
# Find which package contains the upstream job
for upstream_job in package_B.upstream_packages:
    upstream_package = find_package_containing(upstream_job)
    if upstream_package != package_B:
        # B cannot start until A ends
        model.Add(start[B] >= end[upstream_package])
```

---

## Understanding the Output

The solver returns:
- **Status**: OPTIMAL (best possible) or FEASIBLE (good but maybe not best)
- **Objective Value**: The score of the solution
- **Variable Values**: Start/end times and modes for each package

**Example output**:
```
Scenario: Balanced
Status: OPTIMAL
Objective: 847.3
Duration: 42 months
Strategic Coverage: 58%
Technical Debt: 124.5
Packages:
  - customer_golden_record: Month 0-4, Strategic
  - product_daily_sync: Month 2-5, Bridge-to-Model
  - claims_processing: Month 5-12, Strategic
  ...
```

---

## Why This Approach Works

### Advantages of Constraint Programming
1. **Handles complex constraints**: Dependencies, capacity limits, mode restrictions
2. **Optimizes globally**: Considers all packages together, not one at a time
3. **Provides guarantees**: All hard constraints are satisfied
4. **Generates multiple scenarios**: Same framework, different weights

### Limitations
1. **Computational cost**: Large problems (1000+ packages) may need longer solve times
2. **Approximation**: May not find the absolute best solution within time limit
3. **Data sensitivity**: Garbage in = garbage out (bad dependencies = bad schedule)

---

## Troubleshooting

### "INFEASIBLE" - No solution exists
- Check for circular dependencies
- Verify capacity isn't exceeded by single packages
- Consider extending horizon or reducing scope

### "UNKNOWN" - Solver timed out
- Increase `max_time_in_seconds`
- Reduce problem size (aggregate more jobs per package)
- Simplify constraints

### Results seem wrong
- Verify input data (dependencies, effort estimates)
- Check configuration (weights, capacity, horizon)
- Review hard constraint violations in logs
