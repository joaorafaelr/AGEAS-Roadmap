# Subagent: Scenario Optimizer

Use this prompt when spawning subagents to run optimization scenarios.
**Spawn THREE of these in parallel**, one for each scenario.

---

## Prompt Template

```
You are an optimization agent for the roadmap optimizer.

## Your Task
Run the {SCENARIO_NAME} optimization scenario using constraint programming.

## Inputs
- Packages: {WORKSPACE}/intermediate/packages.json
- Configuration: {CONFIG_PATH}
- Output directory: {WORKSPACE}/results/

## Scenario: {SCENARIO_NAME}

Weights for this scenario:
{WEIGHTS_TABLE}

## Algorithm

Use the bundled script at scripts/mrcpsp_optimizer.py, or implement directly:

### 1. Load Data
```python
import json
from ortools.sat.python import cp_model

with open(packages_path) as f:
    packages = json.load(f)
with open(config_path) as f:
    config = json.load(f)
```

### 2. Create Model
```python
model = cp_model.CpModel()
horizon = config['migration_horizon_months']  # e.g., 60
```

### 3. Create Variables

For each package i:
```python
# Mode selection (exactly one)
mode_vars[i] = {
    'build_to_legacy': model.NewBoolVar(f'mode_{i}_btl'),
    'bridge_to_model': model.NewBoolVar(f'mode_{i}_btm'),
    'strategic': model.NewBoolVar(f'mode_{i}_str')
}
model.Add(sum(mode_vars[i].values()) == 1)

# Timing
start_vars[i] = model.NewIntVar(0, horizon, f'start_{i}')
end_vars[i] = model.NewIntVar(1, horizon, f'end_{i}')
```

### 4. Add Constraints

Duration linking (for each mode):
```python
duration = calculate_duration(package, mode)  # See formula in 7-mathematical-formulation.md
model.Add(end_vars[i] == start_vars[i] + duration).OnlyEnforceIf(mode_vars[i][mode])
```

Precedence:
```python
for upstream in package['upstream_packages']:
    upstream_pkg = find_package_containing(upstream)
    if upstream_pkg:
        model.Add(start_vars[i] >= end_vars[upstream_pkg])
```

Resource capacity:
```python
for month in range(horizon):
    month_demand = []
    for pkg in packages:
        for mode in modes:
            is_active = model.NewBoolVar(...)
            # is_active iff (start <= month < end) AND mode selected
            demand = get_resource_demand(pkg, mode)
            month_demand.append(demand * is_active)
    model.Add(sum(month_demand) <= config['team_capacity'])
```

Concurrent execution limits:
```python
for month in range(horizon):
    # Max 2 Strategic clusters in parallel (requires architect focus)
    strategic_active = [...]
    model.Add(sum(strategic_active) <= 2)

    # Max 4 total clusters in-flight (avoid context-switching)
    total_active = [...]
    model.Add(sum(total_active) <= 4)
```

System decommissioning deadlines:
```python
# Clusters depending on decommissioning systems must finish by deadline
for pkg in packages:
    if pkg.get('source_system') in system_deadlines:
        deadline_month = system_deadlines[pkg['source_system']]
        model.Add(end_vars[pkg] <= deadline_month)
```

Strategic approach prerequisites:
```python
# Strategic mode only for clusters belonging to future cores
for pkg in packages:
    if not pkg.get('belongs_to_future_core', False):
        model.Add(mode_vars[pkg]['strategic'] == 0)
```

### 5. Set Objective

```python
# Duration term
max_end = model.NewIntVar(0, horizon, 'max_end')
model.AddMaxEquality(max_end, [end_vars[p] for p in packages])

# Strategic term
strategic_value = sum(
    int(pkg['business_value'] * 100) * mode_vars[pkg]['strategic']
    for pkg in packages
)

# Debt term
debt = sum(
    int(pkg['complexity_score'] * 10) * 2 * mode_vars[pkg]['build_to_legacy'] +
    int(pkg['complexity_score'] * 10) * 1 * mode_vars[pkg]['bridge_to_model']
    for pkg in packages
)

# Combined (note: strategic is negated because we minimize)
objective = (
    {W_DURATION} * max_end +
    -{W_STRATEGIC} * strategic_value +
    {W_DEBT} * debt
)
model.Minimize(objective)
```

### 6. Solve

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 300
status = solver.Solve(model)
```

### 7. Extract Solution

```python
if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    schedule = []
    for pkg in packages:
        start = solver.Value(start_vars[pkg])
        end = solver.Value(end_vars[pkg])
        mode = get_selected_mode(solver, mode_vars[pkg])
        schedule.append({
            'package_id': pkg['package_id'],
            'package_name': pkg['name'],
            'domain': pkg['domain'],
            'start_month': start,
            'end_month': end,
            'duration_months': end - start,
            'selected_mode': mode,
            'effort_days': pkg['total_effort_days'],
            'business_value': pkg['business_value']
        })
```

## Generate Outputs

Save to {WORKSPACE}/results/{SCENARIO_FILE}_result.json:
```json
{
  "scenario_name": "{SCENARIO_NAME}",
  "total_duration_months": 42,
  "packages_by_mode": {
    "build_to_legacy": 32,
    "bridge_to_model": 55,
    "strategic": 40
  },
  "resource_utilization": 0.72,
  "technical_debt_score": 124.5,
  "strategic_coverage": 0.58,
  "schedule": [...],
  "objective_value": 847.3,
  "solver_statistics": {
    "solve_time_seconds": 45.2,
    "status": "OPTIMAL",
    "iterations": 12453
  }
}
```

Save to {WORKSPACE}/results/{SCENARIO_FILE}_solver_log.txt:
- Solver progress output
- Final statistics

## Success Criteria
- Status is OPTIMAL or FEASIBLE
- All packages are scheduled
- No constraint violations
- Return summary: "{SCENARIO_NAME}: {duration} months, {strategic}% strategic, {debt} debt"
```

---

## Three Scenario Configurations

### Fast Exit
```
SCENARIO_NAME = "Fast Exit"
SCENARIO_FILE = "fast_exit"
W_DURATION = 0.6
W_STRATEGIC = 0.1
W_DEBT = 0.3
WEIGHTS_TABLE = """
| Objective | Weight |
|-----------|--------|
| Minimize Duration | 0.6 |
| Maximize Strategic | 0.1 |
| Minimize Tech Debt | 0.3 |
"""
```

### Balanced
```
SCENARIO_NAME = "Balanced"
SCENARIO_FILE = "balanced"
W_DURATION = 0.3
W_STRATEGIC = 0.4
W_DEBT = 0.3
WEIGHTS_TABLE = """
| Objective | Weight |
|-----------|--------|
| Minimize Duration | 0.3 |
| Maximize Strategic | 0.4 |
| Minimize Tech Debt | 0.3 |
"""
```

### Target-First
```
SCENARIO_NAME = "Target-First"
SCENARIO_FILE = "target_first"
W_DURATION = 0.2
W_STRATEGIC = 0.6
W_DEBT = 0.2
WEIGHTS_TABLE = """
| Objective | Weight |
|-----------|--------|
| Minimize Duration | 0.2 |
| Maximize Strategic | 0.6 |
| Minimize Tech Debt | 0.2 |
"""
```

---

## Parallel Execution

Launch all three simultaneously:

```python
# In main agent, spawn all three at once:
Task(
    description="Run Fast Exit optimization",
    prompt=fast_exit_prompt,
    subagent_type="general-purpose",
    run_in_background=True
)
Task(
    description="Run Balanced optimization",
    prompt=balanced_prompt,
    subagent_type="general-purpose",
    run_in_background=True
)
Task(
    description="Run Target-First optimization",
    prompt=target_first_prompt,
    subagent_type="general-purpose",
    run_in_background=True
)

# Then wait for all to complete
```

---

## Expected Duration
- 2-5 minutes per scenario
- All three running in parallel: ~5 minutes total
