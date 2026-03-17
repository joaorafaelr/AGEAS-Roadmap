# 9. Technical Grounding: Effort Estimation from Job Metadata

This document explains how to derive effort estimations from actual job metadata, ensuring roadmap projections are grounded in real technical complexity.

---

## Why Technical Grounding Matters

Effort estimates that come "out of thin air" are often wrong by 2-10x. To make the roadmap optimizer accurate and reliable:

1. **Ground estimates in actual job structure** - Use step counts, transformation complexity, and data volumes
2. **Calibrate with historical data** - If past migrations are available, use them to tune multipliers
3. **Make assumptions explicit** - So stakeholders can challenge and refine them

---

## Job Metadata Available for Estimation

The skill can ingest job metadata in the `data/` folder. Key fields for estimation:

### From Job JSON (`jobs_input.json` or per-job files)

| Field | Description | Impact on Effort |
|-------|-------------|------------------|
| `job_count` | Number of individual jobs in the cluster | Linear scaling |
| `estimated_effort_days` | Pre-calculated effort (if available) | Direct use |
| `complexity` | Low/Medium/High/Critical | Multiplier |
| `data_volume_gb` | Size of data processed | Volume adjustment |
| `source_systems` | Legacy systems involved | Integration complexity |
| `dependencies` | Upstream requirements | Sequencing constraints |

### From Detailed Job Reports (`*_DW_Report.txt`)

These files contain rich metadata per job extracted from source systems:

| Field | Description | Estimation Impact |
|-------|-------------|-------------------|
| `total_steps` | Number of processing steps | Base effort driver |
| `source_tables` | Tables read from | Data understanding effort |
| `target_tables` | Tables written to | Testing effort |
| `source_columns` | Columns in source | Mapping complexity |
| `target_columns` | Columns in target | Transformation scope |
| `transformations` | Number of transformations | Logic complexity |
| `temp_tables` | Intermediate tables | Technical debt indicator |
| `jobs_with_user_code` | Custom code count | Manual review effort |
| `upstream_jobs` | Job dependencies | Sequencing |
| `downstream_jobs` | Dependents | Risk/impact |

---

## Effort Estimation Formulas

### Base Formula (Per Job)

```
base_effort_hours = (
    base_understanding_hours +
    mapping_effort +
    transformation_effort +
    testing_effort +
    integration_effort
)

Where:
  base_understanding_hours = 8  # Every job needs minimum understanding
  mapping_effort = source_columns × 0.1 hours
  transformation_effort = transformations × 0.3 hours
  testing_effort = (source_tables + target_tables) × 1.0 hours
  integration_effort = upstream_jobs × 2.0 hours
```

### Complexity Multipliers

```
complexity_multiplier = {
    "Low":      0.8,
    "Medium":   1.0,
    "High":     1.3,
    "Critical": 1.6
}
```

### Volume Adjustments

```
volume_factor = 1.0 + log10(data_volume_gb + 1) × 0.1

# Examples:
#   1 GB   → 1.0
#   10 GB  → 1.1
#   100 GB → 1.2
#   1 TB   → 1.3
```

### User Code Penalty

Jobs with custom user code require manual review and often refactoring:

```
if has_user_code:
    effort *= 1.5  # 50% additional effort for user code analysis
```

### Final Effort Calculation

```
job_effort_hours = base_effort_hours × complexity_multiplier × volume_factor × user_code_penalty

job_effort_days = job_effort_hours / 8
```

---

## Cluster/Package Estimation

When aggregating jobs into packages:

```
package_effort_days = sum(job_effort_days for job in package)
                    × integration_overhead
                    × risk_buffer

Where:
  integration_overhead = 1.1  # 10% for cross-job integration
  risk_buffer = 1.0 + (max_complexity_score - 1) × 0.1
```

---

## Mode-Adjusted Effort

Different migration approaches have different effort profiles (from config):

| Mode | Duration Multiplier | Description |
|------|---------------------|-------------|
| Build-to-Legacy | 0.8× | Faster but creates tech debt |
| Bridge-to-Model | 1.0× | Standard effort |
| Strategic | 1.3× | More effort, zero tech debt |

---

## Calibration with Historical Data

If you have completed migration data, calibrate the formulas:

1. **Collect actuals**: For each migrated job/cluster, record:
   - Estimated effort (from formula)
   - Actual effort (time tracked)

2. **Calculate calibration factor**:
   ```
   calibration_factor = mean(actual_effort / estimated_effort)
   ```

3. **Apply to future estimates**:
   ```
   calibrated_effort = raw_effort × calibration_factor
   ```

---

## Example: Entities Domain Estimation

Using the data from `data/jobs_input.json`:

```
Job: Entities_Entity_Dimensions
- job_count: 190
- complexity: High (1.3×)
- data_volume_gb: 1900 (volume_factor: 1.33)
- source_systems: ["CCS"]

From detailed report:
- total_steps: ~2000+ (across all jobs)
- transformations: extensive
- jobs_with_user_code: significant

Estimated effort:
  Base: 190 jobs × 80 hours/job average = 15,200 hours
  Complexity: × 1.3 = 19,760 hours
  Volume: × 1.33 = 26,281 hours
  Risk buffer: × 1.1 = 28,909 hours

  Days: 28,909 / 8 = 3,614 person-days

  With 6 FTE: 3,614 / 6 / 20 = ~30 months
```

---

## Data Files Reference

The skill includes the following data files for grounding:

| File | Purpose |
|------|---------|
| `data/jobs_input.json` | Aggregated cluster-level job data |
| `data/aggregated_packages.json` | Pre-computed packages with metrics |
| `data/enhanced_config.json` | Configuration with system deadlines and business rules |
| `data/similarity_scores.json` | Model similarity analysis for effort adjustment |
| `data/*_DW_Report.txt` | Detailed per-job metadata from source systems |

---

## Best Practices

1. **Always validate with SMEs**: Formulas provide a baseline, domain experts should review
2. **Update calibration factors**: After each wave, recalibrate with actuals
3. **Document assumptions**: Every estimate should trace back to source data
4. **Include contingency**: Initial estimates should include 15-25% buffer
5. **Use ranges, not points**: Present estimates as ranges (optimistic/likely/pessimistic)

---

## Integration with the Optimizer

The optimizer reads effort from:

1. **Package JSON** (`total_effort_days` field) - Use this if pre-calculated
2. **Job metadata** - Apply formulas if effort not pre-calculated
3. **Configuration defaults** - Fallback if no data available

Priority: Package JSON > Job Metadata > Configuration Defaults
