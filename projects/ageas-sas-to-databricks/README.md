# Ageas SAS-to-Databricks Migration Project

This folder contains project-specific configuration for the Ageas SAS-to-Databricks migration.

## Project Overview

- **Scope**: 29,000+ SAS programs across Claims, Entities, and Policies domains
- **Target Platform**: Databricks
- **Timeline**: 60 months (5 years)
- **Team**: 2 pods × 3 people = 6 FTEs

## Files

| File | Purpose |
|------|---------|
| `ageas_config.json` | Complete project configuration (system deadlines, business rules, domain settings) |
| `input/` | Place your SAS job JSON files here (or link to existing location) |
| `intermediate/` | Generated during optimization (packages, validation reports) |
| `output/` | Final Excel reports and results |

## Using This Configuration

When running the roadmap optimizer, point to this configuration file:

```
"Where is your configuration file?" → projects/ageas-sas-to-databricks/ageas_config.json
```

## Key Project-Specific Settings

### Future Core Systems

| System | Domain | Description |
|--------|--------|-------------|
| **Polaris** | Policies | Strategic policy administration platform |
| **DC Claims** | Claims | Strategic claims processing platform |
| **EDM** | Entities | Enterprise Data Model for unified entity management |

### System Deadlines

| System | Migration Deadline | Affected Domain |
|--------|-------------------|-----------------|
| CCS | Q3 2026 | Claims |
| DC Policy | Q2 2027 | Policies |
| Tecnisys | Q3 2028 | Policies |
| Cogen | Q3 2028 | Policies |

### Domain Structure

| Domain | Jobs | Subclusters | Foundational Cluster |
|--------|------|-------------|---------------------|
| Claims | 163 | 7 | Claims_Core |
| Entities | 377 | 10+ | Entity_Dimensions |
| Policies | 775 | 25+ | Policy_Core |

### Business Rules

The `ageas_config.json` contains domain-specific rules including:
- **CLM-001 to CLM-004**: Claims domain rules (atomic transitions, NR34/35/36 compliance, CCS deadline)
- **ENT-001 to ENT-004**: Entities domain rules (unified master, EDM as future core)
- **POL-001 to POL-005**: Policies domain rules (Life/Non-Life split, Tecnisys/Cogen deadlines)

## Analytical Models

Bridge-to-Model approach leverages these existing SAS analytical models:
- UNO
- MAOC
- MAE
- MAS

## Relationship to Generic Skill

This configuration file provides all project-specific values that were previously hardcoded in the skill documentation. The generic skill now:
1. Reads this config file at runtime
2. Uses these values for optimization constraints
3. Generates reports with these domain-specific details

Changes to project parameters (deadlines, team size, domain priorities) should be made here, not in the skill itself.
