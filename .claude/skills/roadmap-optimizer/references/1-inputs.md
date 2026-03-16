# 1. Inputs: What Data You Need

This document describes **what information Claude needs** to run the roadmap optimization for any type of system migration or modernization project.

---

## Required Inputs

### 1. System/Job Data (JSON files)

You need one JSON file per item to be migrated, or a single JSON array containing all items. This could be:
- **Data Jobs**: SAS programs, SQL stored procedures, ETL pipelines
- **Applications**: Microservices, modules, batch processes
- **Systems**: Databases, servers, applications
- **Processes**: Business processes, workflows, data flows

**Each item must have:**

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | Unique identifier (e.g., `"CUST_GOLD_LOAD_001"`, `"PaymentService"`) |
| `domain` | string | Business domain: `customer`, `product`, `claims`, `finance`, `operations`, etc. |
| `steps` | array | List of transformation steps, processes, or components |
| `upstream_dependencies` | array | Item IDs that must complete BEFORE this item |
| `downstream_dependencies` | array | Item IDs that depend ON this item |

**Optional but helpful fields:**

| Field | Type | Why It Helps |
|-------|------|--------------|
| `source_systems` | array | External systems the item reads from |
| `volume_indicators.daily_records` | number | Data volume for sizing |
| `volume_indicators.data_size_gb` | number | Storage requirements |
| `volume_indicators.size_factor` | number | Multiplier for effort (0.1 to 10.0) |
| `complexity_indicators.transformation_complexity` | number | How complex the transformations are |
| `business_context.criticality` | string | `low`, `medium`, `high`, or `critical` |
| `business_context.regulatory_requirements` | array | E.g., `["GDPR", "SOX", "HIPAA"]` |
| `technology_stack` | array | Current technologies used (e.g., `["Java", "Oracle", "REST"]`) |
| `target_stack` | array | Target technologies (e.g., `["Python", "PostgreSQL", "GraphQL"]`) |

**Example item (Data Platform Migration):**
```json
{
  "job_id": "CUST_GOLD_LOAD_001",
  "domain": "customer",
  "steps": [
    {
      "step_id": "extract_raw",
      "step_type": "extraction",
      "reads_from": ["customer_raw_db"],
      "writes_to": ["staging_customer"],
      "transformations": ["data_cleansing", "deduplication"]
    }
  ],
  "upstream_dependencies": ["DATA_PREP_001"],
  "downstream_dependencies": ["CUST_ANALYTICS_001"],
  "source_systems": ["CRM_SYSTEM", "BILLING_SYSTEM"],
  "volume_indicators": {
    "daily_records": 50000,
    "data_size_gb": 2.5,
    "size_factor": 1.2
  },
  "business_context": {
    "criticality": "high",
    "regulatory_requirements": ["GDPR", "CCPA"]
  }
}
```

**Example item (Application Modernization):**
```json
{
  "job_id": "PaymentProcessingService",
  "domain": "payments",
  "steps": [
    {
      "step_id": "validate_payment",
      "step_type": "business_logic",
      "apis_called": ["FraudDetectionAPI", "BankValidationAPI"],
      "complexity": "high"
    }
  ],
  "upstream_dependencies": ["UserAuthService"],
  "downstream_dependencies": ["NotificationService", "AuditService"],
  "technology_stack": ["COBOL", "DB2", "CICS"],
  "target_stack": ["Java", "PostgreSQL", "Kubernetes"],
  "volume_indicators": {
    "daily_transactions": 100000,
    "size_factor": 2.5
  },
  "business_context": {
    "criticality": "critical",
    "regulatory_requirements": ["PCI-DSS", "SOX"]
  }
}
```

---

### 2. Configuration File (JSON)

Defines the parameters for the optimization.

**Required settings:**

| Field | Type | Description | Typical Value |
|-------|------|-------------|---------------|
| `migration_horizon_months` | integer | Total time window for migration | 18-60 |
| `team_capacity` | integer | Total people available (FTEs) | 4-12 |

**Optional settings:**

| Field | Description |
|-------|-------------|
| `domain_constraints` | Per-domain earliest start times and priority weights |
| `mode_parameters` | Duration multipliers, tech debt penalties, and cost multipliers per approach |
| `optimization_weights` | Objective weights for each scenario |
| `role_rates` | Hourly rates per role (Architect, Developer, etc.) |
| `system_deadlines` | Decommissioning deadlines for source systems |
| `migration_modes` | Available migration approaches for your context |

**Example configuration (Generic):**
```json
{
  "migration_horizon_months": 36,
  "team_capacity": 8,
  "domain_constraints": {
    "core": { "earliest_start": 0, "priority_weight": 1.0 },
    "customer": { "earliest_start": 3, "priority_weight": 0.9 },
    "finance": { "earliest_start": 6, "priority_weight": 0.8 },
    "reporting": { "earliest_start": 12, "priority_weight": 0.7 }
  },
  "migration_modes": {
    "direct_migration": {
      "description": "Direct migration to target platform",
      "duration_multiplier": 1.3,
      "tech_debt_penalty": 0.0,
      "base_hours": 400,
      "cost_multiplier": 1.3
    },
    "lift_and_shift": {
      "description": "Lift and shift with minimal changes",
      "duration_multiplier": 0.8,
      "tech_debt_penalty": 1.5,
      "base_hours": 200,
      "cost_multiplier": 0.8
    },
    "bridge_approach": {
      "description": "Bridge solution with later convergence",
      "duration_multiplier": 1.0,
      "tech_debt_penalty": 1.0,
      "base_hours": 300,
      "cost_multiplier": 1.0
    }
  },
  "system_deadlines": {
    "LegacyMainframe": {
      "decommission": "2026-12-31",
      "migration_deadline": "2026-Q3",
      "affected_domains": ["core", "finance"]
    },
    "OldCRM": {
      "decommission": "2027-06-30",
      "migration_deadline": "2027-Q1",
      "affected_domains": ["customer"]
    }
  }
}
```

---

### 3. Resource Model

The team structure and role rates inform cost calculations throughout the optimizer.

**Team Composition Examples:**

| Project Size | Structure | Weekly Hours |
|-------------|-----------|-------------|
| Small (< 100 items) | 1 Architect + 2 Developers + 1 QA | 160 hrs/week |
| Medium (100-1000) | 2 Architects + 4 Developers + 2 QA | 320 hrs/week |
| Large (1000+) | 3 Architects + 6 Developers + 3 QA | 480 hrs/week |

**Role Rates (adjust for your region/context):**

| Role | Hourly Rate (USD) | Typical Allocation |
|------|-------------------|-------------------|
| Solution Architect | $150/hr | Design, reviews, complex decisions |
| Senior Developer | $120/hr | Development, technical leadership |
| Developer | $100/hr | Implementation, testing support |
| QA Engineer | $95/hr | Testing, validation |
| Business Analyst | $85/hr | Requirements, UAT support |
| DevOps Engineer | $130/hr | Infrastructure, CI/CD, deployments |

---

### 4. System Decommissioning Dates

Source systems often have hard decommissioning deadlines that constrain the schedule:

**Example deadlines:**

| System | Current Role | Decommission Date | Migration Deadline | Affected Domains |
|--------|-------------|-------------------|-------------------|-----------------|
| Legacy Mainframe | Core Processing | End 2026 | Q3 2026 | Core, Finance |
| Old CRM | Customer Data | End 2027 | Q2 2027 | Customer |
| Legacy ERP | Business Operations | End 2028 | Q3 2028 | Finance, Operations |
| On-Premise Database | All Data | End 2025 | Q4 2025 | All |

```
Constraint: completion_wave(item_i) ≤ migration_deadline(source_system(item_i))
```

---

## What Happens to the Inputs

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Items/Jobs     │ ──► │   Aggregation    │ ──► │  ~50-500       │
│  (JSON files)   │     │   (grouping)     │     │  Packages      │
└─────────────────┘     └──────────────────┘     └────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Excel Report   │ ◄── │   Optimization   │ ◄── │  Configuration │
│                 │     │   (scheduling)   │     │  (constraints) │
└─────────────────┘     └──────────────────┘     └────────────────┘
```

1. **Items** are grouped into **Packages** based on dependencies and domains
2. **Packages** are scheduled using the **Configuration** constraints
3. **Multiple scenarios** are generated with different trade-offs
4. **Excel report** presents all results for stakeholder review

---

## How to Provide Inputs

**Option A: Directory of JSON files**
```
/data/items/
├── CUST_SERVICE_001.json
├── PAYMENT_PROC_001.json
├── INVENTORY_SYNC_001.json
└── ... (more files)
```

**Option B: Single JSON array**
```json
[
  { "job_id": "CUST_SERVICE_001", ... },
  { "job_id": "PAYMENT_PROC_001", ... },
  ...
]
```

**Option C: CSV/Excel that Claude converts to JSON**
- If you have migration data in a spreadsheet, Claude can convert it
- Must include: job_id, domain, upstream/downstream dependencies

---

## Common Questions

**Q: What if I don't have dependency information?**
A: The optimizer will treat items as independent. This reduces optimization quality but still works for basic scheduling.

**Q: What if some items are missing fields?**
A: Claude will use defaults:
- Missing `domain` → `"unknown"`
- Missing `complexity` → calculated from step count
- Missing `effort` → 5 days base × complexity factor

**Q: How accurate does the data need to be?**
A: The optimizer is robust to estimation errors of ±30%. Focus on getting dependencies right - they have the biggest impact on schedule quality.

**Q: Can I use this for non-technical migrations?**
A: Yes! The same principles apply to business process migrations, organizational changes, or any complex project with dependencies.

---

## Migration Type Examples

### Data Platform Modernization
- **Items**: SAS programs, SQL scripts, ETL jobs
- **Domains**: Customer, Product, Finance, Risk, Compliance
- **Dependencies**: Data lineage, table dependencies
- **Modes**: Direct rewrite, Lift-and-shift, Bridge approach

### Application Modernization
- **Items**: Services, modules, batch jobs, APIs
- **Domains**: User Management, Payments, Inventory, Reporting
- **Dependencies**: API calls, shared databases, service communication
- **Modes**: Strangler fig, Big bang rewrite, Microservices extraction

### Cloud Migration
- **Items**: Servers, databases, applications, storage
- **Domains**: Web tier, App tier, Data tier, Network
- **Dependencies**: Network connectivity, shared storage, load balancing
- **Modes**: Rehost, Replatform, Refactor

### Legacy System Replacement
- **Items**: Business functions, integrations, reports, data extracts
- **Domains**: Core banking, Customer service, Risk management
- **Dependencies**: Regulatory approval, data migration, user training
- **Modes**: Parallel run, Phased cutover, Big bang replacement

---

## Terminology

| Term | Definition |
|------|------------|
| Migration Package | Logical grouping of related items that move together |
| Wave | Time-boxed period (typically 2-4 weeks) for migration activities |
| Approach / Mode | Migration strategy (direct, bridge, lift-and-shift, etc.) |
| Domain | Business area or functional grouping |
| Dependencies | Items that must complete before others can start |
| Constraints | Hard rules that cannot be violated (deadlines, resources) |
| Scenario | Complete migration plan with specific approach choices |
