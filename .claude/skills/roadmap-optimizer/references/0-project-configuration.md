# 0. Project Configuration Guide

This skill adapts to ANY migration project through configuration. This guide explains how to set up the skill for your specific context.

---

## Quick Start: Configuration Location

Your project configuration should live **alongside your job data**, not inside the skill. The recommended structure:

```
your-project/
├── input/
│   ├── jobs/               # Your job JSON files
│   │   ├── JOB_001.json
│   │   └── ...
│   └── config.json         # Project-specific configuration ← THIS FILE
├── intermediate/           # Generated during optimization
└── output/                 # Final Excel reports
```

> **Why not inside the skill?**
> The skill should remain generic and reusable. Project-specific configuration lives with your data so you can:
> - Version control project settings separately
> - Have multiple projects using the same skill
> - Share the skill without exposing your project details

---

## Required Configuration Settings

At minimum, your `config.json` needs:

```json
{
  "migration_horizon_months": 36,
  "team_capacity": 6
}
```

| Setting | Type | Description |
|---------|------|-------------|
| `migration_horizon_months` | integer | Total time window for migration (12-120) |
| `team_capacity` | integer | Total FTEs available for migration work |

---

## Optional: Target Platform Configuration

Define your future state systems and which domains qualify for strategic migration:

```json
{
  "future_core_systems": {
    "TargetPlatform": {
      "description": "Strategic target platform",
      "domains": ["domain1", "domain2"],
      "availability_month": 12
    }
  },
  "future_core_domains": ["domain1", "domain2"]
}
```

| Setting | Type | Description |
|---------|------|-------------|
| `future_core_systems` | object | Map of target systems with their properties |
| `future_core_domains` | array | Domains that can use the Strategic approach |

**Impact**: Only packages in `future_core_domains` are eligible for Strategic mode. All others use Build-to-Legacy or Bridge approaches.

---

## Optional: Source System Deadlines

Define when source systems must be decommissioned:

```json
{
  "system_deadlines": {
    "LegacySystem1": {
      "decommission": "2026-12-31",
      "migration_deadline": "2026-Q3",
      "affected_domains": ["domain1", "domain2"]
    },
    "OldDatabase": {
      "decommission": "2027-06-30",
      "migration_deadline": "Q2 2027",
      "affected_domains": ["domain3"]
    }
  }
}
```

| Field | Format | Description |
|-------|--------|-------------|
| `decommission` | ISO date or "YYYY-Qn" | When the system goes offline |
| `migration_deadline` | "YYYY-Qn" or "Qn YYYY" | Latest completion for dependent packages |
| `affected_domains` | array of strings | Domains that depend on this system |

**Note**: Deadline formats supported:
- ISO date: `"2026-12-31"`
- Year-Quarter: `"2026-Q3"`, `"Q3 2026"`, `"Q3-2026"`

---

## Optional: Domain Configuration

Customize domain priorities and start constraints:

```json
{
  "domain_constraints": {
    "core": {
      "earliest_start": 0,
      "priority_weight": 1.0
    },
    "customer": {
      "earliest_start": 3,
      "priority_weight": 0.9
    },
    "reporting": {
      "earliest_start": 12,
      "priority_weight": 0.7
    }
  },
  "foundational_clusters": {
    "domain1": "Foundation_Cluster_ID",
    "domain2": "Core_Setup_Cluster"
  }
}
```

| Setting | Description |
|---------|-------------|
| `earliest_start` | Month number when this domain can begin (0 = immediately) |
| `priority_weight` | Priority multiplier (1.0 = highest, 0.0 = lowest) |
| `foundational_clusters` | Which cluster must be migrated first per domain |

---

## Optional: Migration Mode Parameters

Customize effort multipliers and costs per approach:

```json
{
  "mode_parameters": {
    "build_to_legacy": {
      "description": "Quick migration replicating current behavior",
      "duration_multiplier": 1.8,
      "tech_debt_penalty": 1.5,
      "base_hours": 150,
      "cost_multiplier": 0.8,
      "requires_future_core": false
    },
    "bridge_to_model": {
      "description": "Bridge solution with analytical model integration",
      "duration_multiplier": 1.0,
      "tech_debt_penalty": 1.0,
      "base_hours": 300,
      "cost_multiplier": 1.0,
      "requires_future_core": false
    },
    "strategic": {
      "description": "Full strategic migration to target platform",
      "duration_multiplier": 1.3,
      "tech_debt_penalty": 0.0,
      "base_hours": 400,
      "cost_multiplier": 1.3,
      "requires_future_core": true
    }
  }
}
```

| Parameter | Description |
|-----------|-------------|
| `duration_multiplier` | Factor applied to base effort estimate |
| `tech_debt_penalty` | Technical debt score (0 = no debt, higher = worse) |
| `base_hours` | Starting hours estimate before complexity scaling |
| `cost_multiplier` | Factor applied to cost calculations |
| `requires_future_core` | If true, only available for future_core_domains |

---

## Optional: Role Rates for Cost Calculations

Define hourly rates for cost projections:

```json
{
  "role_rates": {
    "architect": 150,
    "sr_data_engineer": 120,
    "data_engineer": 100,
    "qa_engineer": 95,
    "business_analyst": 85,
    "devops_engineer": 130
  },
  "currency": "USD"
}
```

---

## Optional: Resource Constraints

Fine-tune resource allocation:

```json
{
  "concurrent_limits": {
    "max_strategic_parallel": 2,
    "max_total_parallel": 4
  },
  "resource_demand_tiers": [
    { "effort_threshold": 40, "people": 1 },
    { "effort_threshold": 200, "people": 2 },
    { "effort_threshold": 500, "people": 3 },
    { "effort_threshold": 999999, "people": 4 }
  ]
}
```

---

## Optional: Scenario Optimization Weights

Customize how each scenario prioritizes objectives:

```json
{
  "scenario_weights": {
    "fast_exit": {
      "minimize_duration": 0.6,
      "maximize_strategic": 0.1,
      "minimize_tech_debt": 0.3
    },
    "balanced": {
      "minimize_duration": 0.3,
      "maximize_strategic": 0.4,
      "minimize_tech_debt": 0.3
    },
    "target_first": {
      "minimize_duration": 0.2,
      "maximize_strategic": 0.6,
      "minimize_tech_debt": 0.2
    }
  }
}
```

---

## Optional: Business Rules

Define domain-specific migration rules:

```json
{
  "business_rules": {
    "domain_rules": {
      "claims": {
        "atomic_transition": true,
        "regulatory_requirements": ["Requirement1", "Requirement2"],
        "notes": "Must transition as atomic units"
      }
    },
    "regulatory_compliance": {
      "Requirement1": {
        "description": "Description of requirement",
        "validation_needed": true
      }
    }
  }
}
```

---

## Complete Example Configuration

Here's a complete example for a data platform migration project:

```json
{
  "_project": "Example Data Platform Migration",
  "_created": "2024-01-15",

  "migration_horizon_months": 36,
  "team_capacity": 6,
  "project_start_year": 2024,
  "project_start_month": 1,

  "future_core_systems": {
    "NewDataPlatform": {
      "description": "Strategic target data platform",
      "domains": ["customer", "products", "analytics"],
      "availability_month": 12
    }
  },
  "future_core_domains": ["customer", "products", "analytics"],

  "system_deadlines": {
    "LegacyDB": {
      "decommission": "2026-12-31",
      "migration_deadline": "2026-Q3",
      "affected_domains": ["customer", "products"]
    }
  },

  "domain_constraints": {
    "core": { "earliest_start": 0, "priority_weight": 1.0 },
    "customer": { "earliest_start": 3, "priority_weight": 0.9 },
    "products": { "earliest_start": 6, "priority_weight": 0.85 },
    "analytics": { "earliest_start": 12, "priority_weight": 0.7 }
  },

  "mode_parameters": {
    "build_to_legacy": {
      "duration_multiplier": 1.8,
      "tech_debt_penalty": 1.5,
      "base_hours": 150,
      "cost_multiplier": 0.8
    },
    "bridge_to_model": {
      "duration_multiplier": 1.0,
      "tech_debt_penalty": 1.0,
      "base_hours": 300,
      "cost_multiplier": 1.0
    },
    "strategic": {
      "duration_multiplier": 1.3,
      "tech_debt_penalty": 0.0,
      "base_hours": 400,
      "cost_multiplier": 1.3,
      "requires_future_core": true
    }
  },

  "role_rates": {
    "architect": 150,
    "sr_data_engineer": 120,
    "data_engineer": 100,
    "qa_engineer": 95
  },

  "concurrent_limits": {
    "max_strategic_parallel": 2,
    "max_total_parallel": 4
  }
}
```

---

## Validation

The optimizer will validate your configuration at startup and report:
- Missing required fields
- Invalid value ranges
- Inconsistent settings (e.g., deadline before horizon)

If validation fails, you'll see clear error messages indicating what to fix.

---

## Migration Type Examples

### Data Platform Migration (SAS-to-Databricks, Oracle-to-Snowflake)
- Use `future_core_systems` for your target platform
- Define `system_deadlines` for source system retirement
- Set `mode_parameters` with appropriate effort multipliers

### Application Modernization (Mainframe to Cloud)
- Define services/modules as jobs
- Use `foundational_clusters` for shared infrastructure
- Higher `duration_multiplier` for `strategic` mode

### Cloud Migration (On-Premise to Cloud)
- Simpler mode structure (lift-and-shift vs refactor)
- Focus on `domain_constraints` for phased migration
- Consider parallel team capacity

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No config.json found" | Create config.json in your input directory |
| "Invalid domain constraint" | Ensure domain names match your job data |
| "Future core not available" | Check `availability_month` for target systems |
| "Deadline conflict" | Extend horizon or adjust system deadlines |

---

## See Also

- `references/1-inputs.md` - Job data format
- `references/schemas.md` - Full JSON schemas
- `templates/sample_config.json` - Starter template
