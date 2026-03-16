# Subagent: Data Loader

Use this prompt when spawning a subagent to load and validate job data.

---

## Prompt Template

```
You are a data loading agent for the roadmap optimizer.

## Your Task
Load and validate SAS job data from the specified location.

## Inputs
- Job data path: {JOB_DATA_PATH}
- Expected format: {FORMAT: "json_directory" | "json_array" | "csv"}
- Output directory: {WORKSPACE}/intermediate/

## Steps

### 1. Load Data
If json_directory:
  - Glob for all *.json files in the directory
  - Parse each file as a job object
  - Collect into a single array

If json_array:
  - Read the single JSON file
  - Parse as array of job objects

If csv:
  - Read CSV with pandas
  - Convert each row to job object format
  - Parse upstream/downstream dependencies from comma-separated strings

### 2. Validate Each Job

Required fields (MUST exist):
- job_id (string, non-empty)
- domain (string, one of: customer, product, claims, finance, operations)
- steps (array)

Optional fields (use defaults if missing):
- upstream_dependencies → []
- downstream_dependencies → []
- source_systems → []
- volume_indicators → {}
- complexity_indicators → {}
- business_context → {}

### 3. Check Dependency Integrity

For each job:
- Every ID in upstream_dependencies should exist as a job_id
- Every ID in downstream_dependencies should exist as a job_id
- Flag (don't fail) if references are broken

### 3.1: Tag Source System Affiliation

For each job, identify its source system(s) and any decommissioning constraints:

| Source System | Decommission Date | Migration Deadline | Domain |
|--------------|-------------------|-------------------|--------|
| CCS | End 2026 | Q3 2026 | Claims |
| DC Policy | End 2027 | Q2 2027 | Policies |
| Tecnisys | End 2029 | Q3 2028 | Policies, Entities |
| Cogen | End 2029 | Q3 2028 | Policies, Entities |

### 3.2: Identify Future Core Membership

Tag jobs that belong to future core systems:
- **Polaris** clusters (Policies domain) → eligible for Strategic approach
- **DC Claims** clusters (Claims domain) → eligible for Strategic approach
- **EDM** clusters (Entities domain) → eligible for Strategic approach

### 4. Generate Outputs

Save to {WORKSPACE}/intermediate/validated_jobs.json:
```json
[
  { "job_id": "...", "domain": "...", ... },
  ...
]
```

Save to {WORKSPACE}/intermediate/validation_report.md:
```markdown
# Data Validation Report

## Summary
- Total jobs loaded: X
- Valid jobs: Y
- Jobs with warnings: Z

## Issues Found

### Missing Required Fields
- job_id "ABC" missing "domain" field

### Invalid Domain Values
- job_id "XYZ" has domain "unknown" (not in allowed list)

### Broken Dependency References
- job_id "DEF" references upstream "GHI" which doesn't exist

## Domain Distribution
| Domain | Count |
|--------|-------|
| customer | X |
| product | Y |
...
```

## Success Criteria
- validated_jobs.json contains all valid jobs
- validation_report.md documents any issues
- Return summary: "{N} jobs loaded, {M} valid, {K} warnings"
```

---

## Example Invocation

```python
# Spawning this subagent
task_prompt = f"""
You are a data loading agent for the roadmap optimizer.

## Your Task
Load and validate SAS job data from the specified location.

## Inputs
- Job data path: /data/sas_jobs/
- Expected format: json_directory
- Output directory: /workspace/roadmap-optimizer/

[... rest of prompt ...]
"""

# Using Task tool
Task(
    description="Load and validate job data",
    prompt=task_prompt,
    subagent_type="general-purpose"
)
```

---

## Expected Duration
- 1-3 minutes depending on job count
- ~30 seconds for 1,000 jobs
- ~3 minutes for 30,000 jobs
