# 3. Hard Constraints: Rules That Can NEVER Be Violated

These constraints are **absolute**. The optimizer will never produce a solution that breaks any of these rules. If no valid solution exists within these constraints, the optimization will fail rather than violate them.

---

## Constraint 1: Dependency Order

> **A package cannot start until ALL of its upstream packages are complete.**

### What this means
If Package B depends on Package A, then:
```
Package A:  [████████]
Package B:           [████████]   ✓ OK - B starts after A ends

Package A:  [████████]
Package B:     [████████]         ✗ VIOLATION - B starts before A ends
```

### Why this is non-negotiable
- Upstream packages produce data that downstream packages consume
- Starting downstream before upstream = working with incomplete/missing data
- This would cause the migration to fail, not just be suboptimal

### Implementation detail
```python
# For every package pair where B depends on A:
model.Add(start_vars[B] >= end_vars[A])
```

---

## Constraint 2: Resource Capacity

> **Never schedule more work than the team can handle.**

### What this means
- Default capacity: **6 people** (2 pods × 3 people each)
- At any given month, the sum of all active package resource demands ≤ 6

```
Constraint: Σ hours_allocated(wave_w) ≤ 240 for all waves w
```

### Concurrent Execution Limits

| Limit Type | Maximum | Rationale |
|------------|---------|-----------|
| Strategic clusters in parallel | **2** | High complexity requires architect focus |
| Total clusters in-flight | **4** | Avoid context-switching overhead |
| Clusters per pod | **2** | Maintain quality and focus |

```
Constraint: |{cluster_i : approach(i) = Strategic ∧ in_progress(i, wave_w)}| ≤ 2
Constraint: |{cluster_i : in_progress(i, wave_w)}| ≤ 4
```

### Resource demand by complexity
| Package Complexity | People Required |
|-------------------|-----------------|
| Low (≤ 2.0) | 1 person |
| Medium (2.1 - 4.0) | 2 people |
| High (> 4.0) | 3 people |

### Example
```
Month 5:
  Package A (high complexity):     3 people
  Package B (medium complexity):   2 people
  Package C (low complexity):      1 person
                                   ─────────
  Total:                           6 people ✓ OK (equals capacity)

Month 6:
  Package A (high complexity):     3 people
  Package B (medium complexity):   2 people
  Package D (medium complexity):   2 people
                                   ─────────
  Total:                           7 people ✗ VIOLATION (exceeds capacity)
```

### Why this is non-negotiable
- Scheduling more work than people can do = work doesn't get done
- Overcommitment leads to delays, burnout, quality issues
- The roadmap must be **achievable**, not aspirational

---

## Constraint 3: Timeline Boundary

> **All work must complete within the migration horizon.**

### What this means
- Default horizon: **60 months** (5 years)
- Every package's `end_month` must be ≤ horizon
- No package can extend beyond the cutoff

### Example
```
Horizon: 60 months

Package A: Month 55-58  ✓ OK (ends before horizon)
Package B: Month 58-63  ✗ VIOLATION (ends after horizon)
```

### Why this is non-negotiable
- The horizon represents a business deadline (SAS license expiry, etc.)
- Work that extends beyond isn't a "late delivery" - it's outside scope
- If the optimization can't fit everything, we need to add capacity or extend horizon

---

## Constraint 4: Single Mode Per Package

> **Each package must use exactly ONE migration approach.**

### The three modes
1. **Build-to-Legacy**: Fast but creates technical debt
2. **Bridge-to-Model**: Balanced approach
3. **Strategic**: Slower but aligns with target architecture

### What this means
- A package cannot be "half Strategic, half Bridge"
- The optimizer chooses one mode per package
- Mode affects duration, resource efficiency, and technical debt

### Why this is non-negotiable
- Mixing modes within a package creates inconsistent code
- Testing and validation require a coherent approach
- Tracking progress requires clear categorization

---

## Constraint 5: Package Integrity

> **A package's jobs cannot be split across different time periods.**

### What this means
- All jobs in a package migrate together
- A package starts once and runs continuously until complete
- No "pause and resume" within a package

### Why this is non-negotiable
- Jobs in a package have internal dependencies
- Splitting creates complex handoff problems
- Progress tracking becomes unreliable

---

## Constraint 6: System Decommissioning Deadlines

> **Clusters depending on a source system must complete before that system is decommissioned.**

### What this means
Source systems have hard end-of-life dates. All clusters that read from or depend on a system must finish their transition before the migration deadline.

| System | Current Role | Decommission Date | Migration Deadline | Affected Domain |
|--------|-------------|-------------------|-------------------|-----------------|
| CCS | Claims Core System | End 2026 | **Q3 2026** | Claims |
| DC Policy | Policy Data | End 2027 | **Q2 2027** | Policies |
| Tecnisys | Legacy Non-Life | End 2029 | **Q3 2028** | Policies, Entities |
| Cogen | Legacy Life | End 2029 | **Q3 2028** | Policies, Entities |

```
Constraint: completion_wave(cluster_i) ≤ migration_deadline(source_system(cluster_i))
```

### Why this is non-negotiable
- After decommissioning, the source system no longer exists — data cannot be accessed
- CCS-dependent claims clusters are the most urgent (Q3 2026)
- Missing a deadline means the transition fails for that cluster

---

## Constraint 7: Foundational Cluster Ordering

> **Foundational clusters must complete before their dependent clusters can start.**

Certain clusters are structural prerequisites for entire domain areas:

| Domain | Foundational Cluster | Dependent Clusters |
|--------|---------------------|-------------------|
| Entities | Entity Dimensions | All other Entity clusters |
| Policies | Policy Core | Policy Product clusters |
| Claims | Claims Core | Claims downstream clusters |

### Why this is non-negotiable
- Foundational clusters define the data structures and master records that all other clusters reference
- Starting dependent clusters before foundational ones leads to schema mismatches and data inconsistencies

---

## Constraint 8: Strategic Approach Prerequisites

> **Strategic approach can only be used when the future core system is available.**

```
IF approach(cluster_i) = Strategic
THEN future_core_available(cluster_i) = TRUE
AND  sas_core_system_replicas_available(cluster_i) = TRUE
     before start_wave(cluster_i)

WHERE future_cores ∈ {Polaris, DC_Claims, EDM}
```

### What this means
- Strategic transitions require the corresponding future core system (Polaris, DC Claims, or EDM) to be available
- SAS core system replicas must also be available
- Only clusters belonging to future cores can use the Strategic approach

### Why this is non-negotiable
- Without the target system available, there's nothing to build to strategically
- Attempting Strategic without replicas creates data integrity risks

---

## Domain-Specific Hard Rules

### Claims Domain
| Rule ID | Rule | Rationale |
|---------|------|-----------|
| CLM-001 | Multi-subcluster jobs must transition as atomic units | Ensure data consistency across claims processing |
| CLM-002 | NR34/NR35/NR36 regulatory compliance required | Belgian insurance regulatory requirements |
| CLM-003 | DC Claims is the future core platform | Qualifies for Strategic approach |
| CLM-004 | CCS-dependent clusters must complete by Q3 2026 | CCS decommissioning deadline |

**Structure**: 163 jobs across 7 subclusters; atomic unit is the claims processing chain.

### Entities Domain
| Rule ID | Rule | Rationale |
|---------|------|-----------|
| ENT-001 | No life/non-life split for entities | Unified entity master across all business lines |
| ENT-002 | EDM is the future core master | Qualifies for Strategic approach |
| ENT-003 | Entity Dimensions is foundational | Must complete before other entity clusters |
| ENT-004 | Cross-domain entity references must align | Entities serve Claims and Policies |

**Structure**: 377 jobs across 10+ subclusters; no business line segmentation.

### Policies Domain
| Rule ID | Rule | Rationale |
|---------|------|-----------|
| POL-001 | Life/Non-Life split required | Different regulatory and product structures |
| POL-002 | Policy Core is foundational | Must complete before product-specific clusters |
| POL-003 | Polaris is the future core platform | Qualifies for Strategic approach |
| POL-004 | Tecnisys clusters → Q3 2028 deadline | Source system decommissioning |
| POL-005 | Cogen clusters → Q3 2028 deadline | Source system decommissioning |

**Structure**: 775 jobs across 25+ subclusters; Life vs Non-Life segmentation; multiple legacy sources.

---

## What Happens When Constraints Can't Be Satisfied

If the optimizer cannot find a solution that satisfies all hard constraints:

1. **Solver returns "INFEASIBLE"** - no valid schedule exists
2. **Common causes**:
   - Too many packages for the available capacity and time
   - Circular dependencies in the job data (A depends on B, B depends on A)
   - Impossible timeline (e.g., 1000 packages in 12 months with 6 people)

3. **Resolution options**:
   - Extend the migration horizon
   - Increase team capacity
   - Reduce scope (defer some packages)
   - Check for data errors (bad dependencies)

---

## Summary Table

| Constraint | What It Protects | Consequence If Violated |
|------------|-----------------|------------------------|
| Dependency Order | Data integrity | Migration fails |
| Resource Capacity | Team sustainability | Deadlines missed |
| Timeline Boundary | Business commitment | Out of scope |
| Single Mode | Code consistency | Maintenance nightmare |
| Package Integrity | Progress tracking | Chaos |
| System Deadlines | Decommissioning dates | No source system access |
| Foundational Ordering | Data structure consistency | Schema mismatches |
| Strategic Prerequisites | Target architecture | Build-to-nothing failure |
