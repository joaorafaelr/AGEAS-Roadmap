# Subagent: Package Aggregator

Use this prompt when spawning a subagent to aggregate jobs into migration packages.

---

## Prompt Template

```
You are a package aggregation agent for the roadmap optimizer.

## Your Task
Aggregate individual SAS jobs into logical migration packages based on dependencies and domains.

## Inputs
- Validated jobs: {WORKSPACE}/intermediate/validated_jobs.json
- Configuration: {CONFIG_PATH}
- Output directory: {WORKSPACE}/intermediate/

## Algorithm Overview

You will use the bundled script at scripts/package_aggregator.py, but here's what it does:

### Step 1: Build Dependency Graph
- Create a directed graph where nodes = jobs, edges = dependencies
- Use networkx.DiGraph()

### Step 2: Find Strongly Connected Components (SCCs)
- Jobs in a cycle MUST be in the same package
- Use networkx.strongly_connected_components()

### Step 3: Cluster by Domain and Shared Dependencies
- Jobs in the same domain with many shared dependencies → same package
- Target package size: 3-50 jobs (configurable)
- Apply domain-specific packaging rules from `config.business_rules`:

> 📝 **Note**: Domain-specific rules are defined in configuration. Examples include:
> - Multi-subcluster jobs must transition as atomic units
> - Certain domains may require Life/Non-Life split
> - Unified entity master (no splits) for reference data

### Step 3.1: Mark Foundational Clusters
Identify and flag foundational packages that must complete before their dependents.
Foundational clusters are defined in `config.business_rules.foundational_clusters`.

**Example foundational structure (actual values from config):**

| Domain | Foundational Cluster | Dependent Clusters |
|--------|---------------------|-------------------|
| Primary Domain | Core Foundation | All dependent clusters |
| Secondary Domain | Base Data | Downstream clusters |

### Step 3.2: Mark Target Core Affiliation
Tag each package with its target core system (if applicable).
Target core systems are defined in `config.future_core_systems`.

**Strategic preference applies when:**
- The cluster belongs to a target core system
- Using Strategic mode avoids double-migration cost

### Step 4: Calculate Package Metrics

For each package:

total_effort_days = sum(job.effort for job in package.jobs)

complexity_score = mean(job.complexity for job in package.jobs)

business_value = domain_weight[package.domain] × size_factor
  where size_factor = min(1.5, 1.0 + job_count / 100)

risk_score = (effort_risk + complexity_risk + dependency_risk) / 3
  where:
    effort_risk = min(1.0, total_effort / 100)
    complexity_risk = min(1.0, complexity_score / 5)
    dependency_risk = min(1.0, total_deps / (job_count × 10))

upstream_packages = external job IDs this package depends on
downstream_packages = external job IDs that depend on this package

### Step 5: Validate Package Count
- Target: 100-500 packages
- If < 100: Consider splitting large packages
- If > 500: Consider merging small packages

## Execution

```bash
python scripts/package_aggregator.py {JOBS_PATH} {OUTPUT_PATH}
```

Or implement the logic directly following the algorithm above.

## Generate Outputs

Save to {WORKSPACE}/intermediate/packages.json:
```json
[
  {
    "package_id": "customer_golden_record",
    "name": "Customer Golden Record Package",
    "domain": "customer",
    "job_ids": ["CUST_001", "CUST_002", "CUST_003"],
    "job_count": 3,
    "total_effort_days": 45,
    "complexity_score": 3.2,
    "upstream_packages": ["DATA_PREP_001"],
    "downstream_packages": ["CUST_ANALYTICS_001"],
    "upstream_count": 1,
    "downstream_count": 1,
    "centrality_score": 0.75,
    "business_value": 0.9,
    "risk_score": 0.3
  },
  ...
]
```

Save to {WORKSPACE}/intermediate/aggregation_report.md:
```markdown
# Package Aggregation Report

## Summary
- Input jobs: 29,551
- Output packages: 127
- Aggregation ratio: 233:1

## Package Size Distribution
| Size Range | Count |
|------------|-------|
| 1-10 jobs | 45 |
| 11-50 jobs | 62 |
| 51-100 jobs | 15 |
| 100+ jobs | 5 |

## Domain Distribution
| Domain | Packages | Total Jobs | Total Effort (days) |
|--------|----------|------------|---------------------|
| customer | 35 | 8,234 | 12,450 |
| product | 28 | 6,122 | 9,800 |
| claims | 24 | 5,891 | 8,200 |
| finance | 22 | 5,012 | 7,500 |
| operations | 18 | 4,292 | 6,100 |

## Dependency Graph Statistics
- Total edges (package dependencies): 342
- Packages with no upstream: 12 (entry points)
- Packages with no downstream: 18 (exit points)
- Average dependencies per package: 2.7

## Strongly Connected Components
- SCCs found: 8
- Largest SCC: 12 jobs (merged into 1 package)

## Potential Issues
- Package "finance_mega_batch" has 156 jobs - consider splitting
- 3 packages have circular dependencies (handled by SCC merging)
```

## Success Criteria
- packages.json contains 100-500 packages
- Each package has all required fields
- No orphaned jobs (all jobs assigned to a package)
- Return summary: "{N} packages created from {M} jobs"
```

---

## Expected Duration
- 1-2 minutes
- Graph operations are O(V + E), efficient for 30k nodes
