# 4. Soft Constraints: Preferences That CAN Be Traded Off

These constraints represent **preferences**, not absolutes. The optimizer will try to satisfy them, but will bend them if necessary to find a better overall solution.

---

## How Soft Constraints Work

Unlike hard constraints (which cause failure if violated), soft constraints influence the **objective function**. The optimizer:

1. Calculates a "cost" when a soft constraint is bent
2. Balances that cost against other objectives
3. May accept some cost to improve overall quality

**Example**: "Prefer Strategic mode" is a soft constraint. The optimizer might choose Bridge mode for some packages if it significantly reduces duration.

---

## Soft Constraint 1: Minimize Total Duration

> **Prefer shorter overall migration timelines.**

### How it's applied
- The objective function includes `weight × max_end_month`
- Higher weight = more aggressive timeline compression

### Trade-off examples
| Decision | Duration Impact | Other Impact |
|----------|-----------------|--------------|
| Use Build-to-Legacy | -20% duration | +100% tech debt |
| Parallelize aggressively | Shorter | Higher utilization risk |
| Strategic mode | +30% duration | Zero tech debt |

### Scenario weights
- **Fast Exit**: 60% (heavily prioritized)
- **Balanced**: 30% (moderate)
- **Target-First**: 20% (less important)

---

## Soft Constraint 2: Maximize Strategic Coverage

> **Prefer Strategic migration mode when possible.**

### Why we prefer Strategic
- Aligns with target architecture
- Zero technical debt
- No rework needed later
- Uses staging/replica environment initially, upgraded when production is ready
- **For clusters targeting future core systems, Strategic avoids the double-cost of Build-from-Legacy**

### How it's applied
```
objective += weight × sum(business_value × is_strategic[package])
```

Higher business value packages contribute more when using Strategic mode.

### Trade-off examples
| Package Value | Strategic Worth | Might Accept Non-Strategic If... |
|--------------|-----------------|----------------------------------|
| High (0.9) | Very valuable | Reduces duration by 6+ months |
| Medium (0.6) | Moderate | Reduces duration by 3+ months |
| Low (0.3) | Minor | Almost any duration benefit |

### Scenario weights
- **Fast Exit**: 10% (low priority)
- **Balanced**: 40% (significant)
- **Target-First**: 60% (dominant)

---

## Soft Constraint 3: Minimize Technical Debt

> **Prefer approaches that don't create future rework.**

### How technical debt accumulates
| Mode | Debt Penalty Formula |
|------|---------------------|
| Build-to-Legacy | `complexity × 2` |
| Bridge-to-Model | `complexity × 1` |
| Strategic | `0` (no debt) |

### Example calculation
```
Package with complexity 4.0:
  - Build-to-Legacy: 4.0 × 2 = 8.0 debt points
  - Bridge-to-Model: 4.0 × 1 = 4.0 debt points
  - Strategic:       0 debt points
```

### Trade-off consideration
- High-complexity packages have bigger debt impact
- The optimizer weighs: "Is saving 2 months worth 20 debt points?"

### Scenario weights
- **Fast Exit**: 30%
- **Balanced**: 30%
- **Target-First**: 20%

---

## Soft Constraint 4: Domain Priority Weights

> **Some business domains are more important than others.**

### Default domain weights
| Domain | Weight | Interpretation |
|--------|--------|----------------|
| Customer | 1.0 | Highest priority |
| Claims | 0.95 | Near-highest |
| Product | 0.9 | High |
| Finance | 0.8 | Medium |
| Operations | 0.7 | Lower |

### How it's applied
- Higher-weight domains get preferential scheduling
- Their packages are more likely to start earlier
- Strategic mode is more likely for high-weight domains

### When to adjust
- If Finance is critical for year-end: increase to 1.0
- If Operations can wait: decrease to 0.5
- This is a **business decision**, not a technical one

---

## Soft Constraint 5: Resource Efficiency by Mode

> **Some modes use team capacity more efficiently.**

### Mode efficiency factors
| Mode | Efficiency | What It Means |
|------|------------|---------------|
| Build-to-Legacy | 1.0 | Baseline efficiency |
| Bridge-to-Model | 0.9 | Slightly less efficient |
| Strategic | 0.8 | Requires more ramp-up time |

### Practical impact
- Strategic mode needs 25% more "effective capacity"
- A 3-person package in Strategic mode "feels like" 3.75 people
- This softly discourages Strategic when capacity is tight

---

## Soft Constraint 6: Domain Earliest Start

> **Some domains shouldn't start until a certain month.**

### Default settings
| Domain | Earliest Start | Reason |
|--------|---------------|--------|
| Customer | Month 0 | Start immediately |
| Claims | Month 0 | Start immediately |
| Product | Month 6 | After initial learnings |
| Operations | Month 6 | After initial learnings |
| Finance | Month 12 | After processes stabilize |

### How it's applied
- Packages in delayed domains prefer later start times
- But if there's slack capacity early, they CAN start sooner
- This is a preference, not a hard block

---

## Soft Constraint 7: Risk Distribution

> **Spread high-risk packages across the timeline.**

### What constitutes "high risk"
- Risk score > 0.7
- High complexity + large effort
- Many dependencies (upstream or downstream)

### How it's applied
- Penalty for having multiple high-risk packages active simultaneously
- Encourages sequential rather than parallel high-risk work

### Why it matters
- Clustering risk = one problem affects multiple packages
- Spreading risk = better chance of early problem detection

---

## Adjusting Soft Constraints

Users can modify these preferences by:

1. **Changing scenario weights** in the configuration:
   ```json
   "optimization_weights": {
     "custom_scenario": {
       "minimize_duration": 0.4,
       "maximize_strategic": 0.4,
       "minimize_tech_debt": 0.2
     }
   }
   ```

2. **Adjusting domain priorities**:
   ```json
   "domain_constraints": {
     "finance": { "priority_weight": 1.0 }  // Increase Finance priority
   }
   ```

3. **Changing mode parameters**:
   ```json
   "mode_parameters": {
     "strategic": { "duration_multiplier": 1.1 }  // Make Strategic faster
   }
   ```

---

## Summary: Hard vs Soft

| Aspect | Hard Constraints | Soft Constraints |
|--------|-----------------|------------------|
| Violation | Causes failure | Adds cost to objective |
| Purpose | Ensure validity | Guide optimization |
| Flexibility | None | Can be traded off |
| User control | Cannot disable | Can adjust weights |
| Examples | Dependencies, capacity | Duration, strategic coverage |

---

## Approach Cost Profiles

Understanding the true cost of each approach is critical for informed trade-offs.

### Cost Ranking (Current Implementation Cost)

| Rank | Approach | Relative Cost | Typical Hours | Rationale |
|------|----------|---------------|---------------|-----------|
| 1 (LOWEST) | Bridge-to-Model | 1.0× (baseline) | ~150 hours | Reuses source output directly; minimal rework; leverages existing analytical models |
| 2 (EQUAL) | Strategic | 2.9× | ~438 hours | Full target model redesign; complete transformation to future core systems |
| 2 (EQUAL) | Bridge-from-Legacy | 2.9× | ~438 hours | Same complexity as Strategic; requires dual-run infrastructure, reconciliation effort, variance monitoring |

### Total Cost of Ownership (Including Future Migration)

| Approach | Current Cost | Future Migration Cost | Total Cost | Recommendation |
|----------|--------------|----------------------|------------|----------------|
| Strategic (Future Cores) | 438 hours | €0 (final state) | **438 hours** | **Preferred for future cores** |
| Bridge-from-Legacy (Future Cores) | 438 hours | +438 hours (eventual migration) | **876 hours** | Avoid for future cores |
| Bridge-from-Legacy (Non-Future Cores) | 438 hours | €0 (legacy maintained) | **438 hours** | Acceptable for non-future cores |

### Cost Components by Phase

#### Strategic Approach (~438 hours) — Future Cores Only
**Applicable to:** Clusters belonging to future core systems (defined in `config.future_core_systems`)
**Requires:** Source system replicas available for validation

| Phase | Hours | % of Total |
|-------|-------|------------|
| Analysis & Design | 88 | 20% |
| Development | 175 | 40% |
| Testing & Validation | 131 | 30% |
| Go-Live & Cutover | 44 | 10% |

#### Bridge-to-Model Approach (~150 hours)
**Constraint:** Only applicable when target go-live and target migration dates are NOT live during product instantiation

| Phase | Hours | % of Total |
|-------|-------|------------|
| Source Output Analysis | 30 | 20% |
| Minimal Transformation | 38 | 25% |
| Integration & Validation | 52 | 35% |
| Transition Planning | 30 | 20% |

#### Bridge-from-Legacy Approach (~438 hours)
**Same complexity as Strategic.** Risk: future cores will require additional migration cost.

| Phase | Hours | % of Total |
|-------|-------|------------|
| Analysis & Bridging Design | 88 | 20% |
| Dual-Run Development | 175 | 40% |
| Dual-Run Execution & Validation | 131 | 30% |
| Cutover & Stabilisation | 44 | 10% |

### Cost Calculation Formula

```
Cost(cluster_i) = base_cost(approach_i) × complexity_multiplier(cluster_i) × risk_adjustment(cluster_i) + future_migration_cost(cluster_i)

Where:
  base_cost(Strategic) = 438 hours
  base_cost(Bridge-to-Model) = 150 hours
  base_cost(Bridge-from-Legacy) = 438 hours (same as Strategic)
  complexity_multiplier ∈ [0.8, 1.5] based on complexity score
  risk_adjustment ∈ [1.0, 1.3] based on risk score
  future_migration_cost = 438 hours IF (Bridge-from-Legacy AND future_core) ELSE 0
```

---

## Approach Selection Decision Matrix

### Selection Criteria

| Criterion | Strategic | Bridge-to-Model | Bridge-from-Legacy |
|-----------|-----------|-----------------|-------------------|
| Future core availability | Required (defined in config) | Not required | Not required |
| Target model available | Required | Analytical model exists | Not required |
| Source system replicas | Required | Not required | Not required |
| Go-live status | Future cores must be live | Target/migration dates must NOT be live | Any status |
| Similarity score | High (>70%) | Medium (50-70%) | Low (<50%) |
| Complexity score | Any | Low-Medium | Medium-High |
| Time pressure | Low (can wait) | Medium | High (urgent) |
| Strategic importance | High | Medium | Lower |

### Decision Rules

```
# Strategic Approach — For Future Cores Only (Preferred to avoid future migration cost)
IF cluster_belongs_to_future_core  # Defined in config.future_core_systems
   AND future_core_available
   AND source_system_replicas_available
   AND similarity_score > 70%
   AND strategic_importance = HIGH
THEN approach = Strategic

# Bridge-to-Model Approach — Conditional on Go-Live Status
ELSE IF analytical_model_exists
   AND similarity_score ∈ [50%, 70%]
   AND target_go_live_date NOT live
   AND target_migration_date NOT live
   AND product_instantiation_in_roadmap = TRUE
THEN approach = Bridge-to-Model

# Bridge-from-Legacy Approach — Default/Fallback (WARNING: future cores incur double cost)
ELSE IF time_pressure = HIGH
   OR (target_model_available = FALSE AND deadline_imminent)
   OR (target_go_live_date = live OR target_migration_date = live)
THEN approach = Bridge-from-Legacy
   IF cluster_belongs_to_future_core THEN add_future_migration_cost
```

### Future Core Systems

The Strategic approach is exclusively applicable to clusters belonging to future core systems and should be **preferred** to avoid double cost.

Future core systems are defined in your project's `config.json` under `future_core_systems`:

```json
{
  "future_core_systems": {
    "TargetPlatform1": {
      "description": "Strategic target for Domain A",
      "domains": ["domain_a"],
      "availability_month": 12
    },
    "TargetPlatform2": {
      "description": "Strategic target for Domain B",
      "domains": ["domain_b"],
      "availability_month": 18
    }
  },
  "future_core_domains": ["domain_a", "domain_b"]
}
```

| Configuration Key | Purpose |
|------------------|---------|
| `future_core_systems` | Defines available target platforms with their domains and availability |
| `future_core_domains` | List of domains that qualify for Strategic approach |

> 📝 **Note**: Only clusters belonging to `future_core_domains` can use the Strategic approach. All others must use Bridge or Build-to-Legacy approaches.

### Approach Transition Paths

```
Bridge-from-Legacy → Bridge-to-Model → Strategic
         ↓                  ↓               ↓
    (Temporary)        (Interim)        (Final)
```

Clusters may transition through approaches as target models become available.

---

## Risk Management

### Risk Categories

| Category | Description | Mitigation |
|----------|-------------|------------|
| Technical | Complex transformations, data quality issues | POC validation, incremental delivery |
| Resource | Team capacity, skill gaps | Cross-training, buffer allocation |
| Dependency | System availability, data dependencies | Dependency mapping, early escalation |
| Timeline | Decommissioning deadlines, scope creep | Regular reviews, scope governance |
