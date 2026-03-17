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

**Example deadlines (from configuration):**

| System | Current Role | Decommission Date | Migration Deadline | Affected Domain |
|--------|-------------|-------------------|-------------------|-----------------|
| Legacy System A | Core Processing | End Year X | Quarter Before | Primary Domain |
| Legacy System B | Data Source | End Year Y | Quarter Before | Secondary Domain |
| Legacy System C | Supporting | End Year Z | Quarter Before | Multiple Domains |

> 📝 **Note**: Actual system deadlines are defined in `config.json` under `system_deadlines`. The examples above are illustrative. Your configuration might include systems like:
> - CCS, Tecnisys, Cogen (data platforms)
> - Legacy Mainframe, Old CRM (enterprise systems)
> - On-premise databases (infrastructure)

```
Constraint: completion_wave(cluster_i) ≤ migration_deadline(source_system(cluster_i))
```

### Why this is non-negotiable
- After decommissioning, the source system no longer exists — data cannot be accessed
- System-dependent clusters with the earliest deadlines are the most urgent
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

> **Strategic approach can only be used when the target core system is available.**

```
IF approach(cluster_i) = Strategic
THEN target_system_available(cluster_i) = TRUE
AND  source_system_replicas_available(cluster_i) = TRUE
     before start_wave(cluster_i)

WHERE target_systems are defined in config.future_core_systems
```

### What this means
- Strategic transitions require the corresponding target system to be available
- Source system replicas must also be available for dual-run validation
- Only clusters belonging to target core systems (defined in config) can use the Strategic approach

> 📝 **Note**: Target systems are defined in `config.json` under `future_core_systems`. Examples include:
> - **Data Platform Migrations**: Target data warehouse, lakehouse, or analytics platform
> - **Application Modernization**: Target microservices platform, cloud runtime
> - **Enterprise Systems**: New ERP, CRM, or core banking platform

### Why this is non-negotiable
- Without the target system available, there's nothing to build to strategically
- Attempting Strategic without replicas creates data integrity risks

---

## Domain-Specific Hard Rules

Domain-specific rules are defined in your project's `config.json` under `business_rules.domain_rules`. These rules encode your organization's specific requirements.

### Example Rule Structure

Rules should be defined per domain with the following pattern:

```json
{
  "business_rules": {
    "domain_rules": {
      "domain_name": {
        "rules": [
          {
            "rule_id": "DOM-001",
            "rule": "Description of the rule",
            "rationale": "Why this rule exists",
            "enforcement": "hard"
          }
        ],
        "structure": {
          "job_count": 163,
          "subclusters": 7,
          "notes": "Atomic unit description"
        }
      }
    }
  }
}
```

### Common Rule Categories

| Category | Example Rules |
|----------|--------------|
| **Atomic Transitions** | Multi-component jobs must transition together |
| **Regulatory Compliance** | Specific regulatory requirements (GDPR, SOX, industry-specific) |
| **Future Core Designation** | Which systems qualify for Strategic approach |
| **System Deadlines** | Decommissioning-driven constraints |
| **Domain Segmentation** | Whether to split by business line (e.g., Life/Non-Life for insurance) |

### Sample Domain Configuration

**Domain A (with unified structure):**
```json
{
  "domain_a": {
    "rules": [
      {"rule_id": "A-001", "rule": "No business-line split", "rationale": "Unified master data"},
      {"rule_id": "A-002", "rule": "System X is future core", "rationale": "Strategic target"}
    ],
    "structure": {"job_count": 377, "subclusters": 10, "notes": "No segmentation"}
  }
}
```

**Domain B (with segmented structure):**
```json
{
  "domain_b": {
    "rules": [
      {"rule_id": "B-001", "rule": "Segment by business line", "rationale": "Different regulatory structures"},
      {"rule_id": "B-002", "rule": "Core cluster is foundational", "rationale": "Must complete first"}
    ],
    "structure": {"job_count": 775, "subclusters": 25, "notes": "Life vs Non-Life segmentation"}
  }
}
```

> 📝 **Note**: The specific rule IDs, system names, and job counts above are examples. Define your actual rules in your project's configuration file. See `references/0-project-configuration.md` for the complete configuration guide.

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
