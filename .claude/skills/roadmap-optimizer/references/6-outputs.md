# 6. Outputs: What You Get Back

This document describes **what the optimizer produces** and how to interpret it.

---

## Primary Output: Excel Workbook (Financial Model)

The main deliverable is a **12-sheet, formula-driven Excel workbook**: `migration_roadmap_report.xlsx`

### Design Principles

| Convention | Meaning |
|------------|---------|
| **Blue font** | Editable input — change it and formulas recalculate |
| **Black font** | Formula cell — computed from other cells |
| **Yellow background** | Key assumption requiring attention |
| **Named ranges** | Improve formula readability (e.g. `team_capacity`, `fte_daily_rate`) |
| **Excel Tables** | Structured tables enabling VLOOKUP/INDEX-MATCH |
| **Conditional formatting** | Color scales, data bars, icon-based rules |

---

### Sheet 1: Assumptions

**Purpose**: Single source of truth for all tunable parameters

**Contains**:
```
┌─────────────────────────────────────────────────────────────────┐
│  ASSUMPTIONS & PARAMETERS                                       │
│  Blue cells are editable — change them and everything updates   │
│                                                                 │
│  GENERAL PARAMETERS                                             │
│  Migration Horizon (months)     [60]   ← blue font, yellow bg  │
│  Team Capacity                  [6]                             │
│  FTE Daily Cost Rate ($)        [$850]                          │
│  Working Days per Month         [20]                            │
│  Risk Buffer Factor             [0.25]                          │
│                                                                 │
│  MODE PARAMETERS (ModeTable)                                    │
│  ┌─────────────────┬──────┬──────┬──────┬──────┐               │
│  │ Mode            │ Dur× │ Debt │ Eff  │ Cost×│               │
│  ├─────────────────┼──────┼──────┼──────┼──────┤               │
│  │ Build-to-Legacy │ 0.70 │ 3.00 │ 1.20 │ 0.80 │               │
│  │ Bridge-to-Model │ 1.00 │ 1.50 │ 1.00 │ 1.00 │               │
│  │ Strategic       │ 1.40 │ 0.50 │ 0.80 │ 1.30 │               │
│  └─────────────────┴──────┴──────┴──────┴──────┘               │
│                                                                 │
│  DOMAIN PRIORITY & EARLIEST START (DomainTable)                 │
│  SCENARIO OBJECTIVE WEIGHTS (ScenarioWeightsTable)              │
│  RISK ASSESSMENT WEIGHTS                                        │
└─────────────────────────────────────────────────────────────────┘
```

**Named ranges**: `horizon_months`, `team_capacity`, `fte_daily_rate`, `working_days_month`, `risk_buffer_factor`, `risk_w_complexity`, `risk_w_dependency`, `risk_w_bv`, `risk_w_volume`

---

### Sheet 2: Package_Data

**Purpose**: Raw package inventory — the data foundation

**Contains** (as an Excel Table `PackageData`):
| Column | Description |
|--------|-------------|
| Package_ID | Unique identifier |
| Name | Human-readable name |
| Domain | Business domain |
| Job_Count | Number of SAS jobs |
| Effort_Days | Total effort estimate |
| Complexity | Score (1.0–5.0) with data bars |
| Business_Value | Importance (1–10) |
| Risk_Score | Risk assessment (1.0–5.0) with color scale |
| Upstream_Count | Incoming dependencies |
| Downstream_Count | Outgoing dependencies |

**Features**: Data bars on Complexity, color scale (green→red) on Risk Score, auto-filter, frozen headers.

---

### Sheets 3–5: Schedule_FastExit / Schedule_Balanced / Schedule_TargetFirst

**Purpose**: Detailed schedule for each scenario

**Contains** (as Excel Tables):
| Column | Description |
|--------|-------------|
| Package_ID | Identifier |
| Name | Package name |
| Domain | Business domain |
| Start_Month | When work begins |
| End_Month | When work completes |
| Duration | **Formula**: `=End_Month - Start_Month` |
| Mode | Migration mode (conditional formatting for colors) |
| Effort_Days | Total effort |
| Business_Value | Importance score |

**Mode color-coding** (via conditional formatting rules, not hardcoded fills):
- 🔴 Build-to-Legacy → light red (#FFCDD2)
- 🔵 Bridge-to-Model → light indigo (#C5CAE9)
- 🟢 Strategic → light green (#C8E6C9)

---

### Sheet 6: Executive_Summary

**Purpose**: One-page overview for leadership — **all values are formulas**

```
┌─────────────────────────────────────────────────────────────────┐
│  MIGRATION ROADMAP — EXECUTIVE SUMMARY                          │
│  Generated: March 13, 2026                                      │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   =25    │  │    3     │  │  =60     │  │   =6     │       │
│  │ Packages │  │ Scenarios│  │ Horizon  │  │ Capacity │       │
│  │ (formula)│  │          │  │ (formula)│  │ (formula)│       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                 │
│  SCENARIO COMPARISON                                            │
│  ┌────────────┬──────────┬───────────┬──────────┬──────┐       │
│  │ Metric     │ FastExit │ Balanced  │ Target   │ Best │       │
│  ├────────────┼──────────┼───────────┼──────────┼──────┤       │
│  │ Duration   │ =MAX(E)  │ =MAX(E)   │ =MAX(E)  │=MIN  │       │
│  │ Strategic% │=COUNTIF  │=COUNTIF   │=COUNTIF  │=MAX  │       │
│  │ BtL Count  │=COUNTIF  │=COUNTIF   │=COUNTIF  │=MIN  │       │
│  │ …          │          │           │          │      │       │
│  └────────────┴──────────┴───────────┴──────────┴──────┘       │
│                                                                 │
│  RECOMMENDATIONS (auto-generated from results)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Sheet 7: Scenario_Comparison

**Purpose**: Detailed metrics comparison — all formulas

**Contains**:
- Side-by-side metrics table with "Best ✓" column
- Duration, Strategic %, Tech Debt Score, Mode counts, Total Effort
- Mode distribution chart data table
- **Stacked bar chart** for mode distribution (linked to formula cells)

---

### Sheet 8: Timeline_Gantt

**Purpose**: Visual Gantt chart

**Layout**:
```
Package Name          │ Mode │ M0 │ M1 │ M2 │ M3 │ M4 │ M5 │...
──────────────────────┼──────┼────┼────┼────┼────┼────┼────┼───
Customer Onboarding   │ BtL  │████████████│    │    │    │...
Pricing Engine        │ Str  │    │████████████████│    │...
Claims Adjudication   │ BtM  │    │    │    │████████████│...
```

**Color coding**: 🟥 Build-to-Legacy, 🟦 Bridge-to-Model, 🟩 Strategic

---

### Sheet 9: Effort_Cost_Model *(NEW)*

**Purpose**: Full cost analysis driven by Assumptions sheet

**Contains**:
- **Scenario Cost Summary**: Total Effort, Total Cost (=Effort × FTE_Daily_Rate), Duration, Cost/Month
- **Delta column**: difference between max and min scenario
- **Monthly Burn Rate** table (M0–M35) per scenario using SUMPRODUCT formulas
- **Line chart**: monthly burn rate by scenario

**Key formula**: `Total Cost = SUM(Schedule_X!Effort) × Assumptions!fte_daily_rate`

---

### Sheet 10: Risk_Assessment *(NEW)*

**Purpose**: Risk scoring with weighted formula model

**Contains**:
| Column | Formula |
|--------|---------|
| Weighted_Risk | `=MIN(1, (Complexity/5×W1 + Deps/10×W2 + (10-BV)/10×W3 + Jobs/50×W4))` |
| Risk_Category | `=IF(risk>0.7,"Critical", IF(>0.4,"High", IF(>0.2,"Medium","Low")))` |
| Risk_Adj_Duration | `=VLOOKUP(duration) × (1 + Risk × risk_buffer_factor)` |

**Features**:
- Heat-map conditional formatting on risk score (green → amber → red)
- Category badges (Critical=red, High=amber, Medium=green, Low=cyan)
- Summary section: count and % per category
- **Pie chart** for risk distribution

---

### Sheet 11: Dependency_Analysis *(NEW)*

**Purpose**: Dependency chain analysis and critical path detection

**Contains**:
| Column | Formula |
|--------|---------|
| Total_Deps | `=Upstream + Downstream` |
| Fan_Out_Score | `=Downstream × (1 + Complexity/5)` |
| Critical_Path | `=IF(AND(Downstream ≥ threshold, Complexity ≥ threshold), "Critical Path", "")` |
| Impact_Score | `=Downstream × Business_Value / 10` |

**Features**:
- Data bars on Fan-Out Score
- Color scale on Impact Score
- Critical Path cells highlighted in red
- Domain interconnection matrix
- Summary: total critical items, max fan-out, avg deps, highest-impact package (INDEX/MATCH)

---

### Sheet 12: Data_Appendix

**Purpose**: Configuration recap and reference data

**Contains**:
- Configuration values (formulas referencing Assumptions sheet)
- Domain breakdown (COUNTIF/SUMIF from Package_Data)
- Mode distribution per scenario (COUNTIF from Schedule sheets)
- Report metadata (timestamp, version, conventions)

---

## How to Read the Report

### Quick Assessment (2 minutes)
1. Open **Executive_Summary** → review KPI cards and scenario comparison
2. Scan the **Recommendations** section
3. Glance at **Effort_Cost_Model** for budget numbers

### Detailed Analysis (15 minutes)
1. **Scenario_Comparison** → understand trade-offs with chart
2. **Timeline_Gantt** → visual flow of the migration
3. **Risk_Assessment** → identify Critical/High packages
4. **Dependency_Analysis** → find critical-path items

### Deep Dive (1 hour)
1. **Assumptions** → adjust parameters and watch formulas recalculate
2. Filter **Package_Data** by domain
3. Drill into **Schedule_[Scenario]** sheets
4. Compare costs in **Effort_Cost_Model** across scenarios

### What-If Analysis
1. Go to **Assumptions** sheet
2. Change a blue cell (e.g., increase `team_capacity` from 6 to 8)
3. All downstream sheets recalculate automatically
4. Compare before/after in the **Executive_Summary**

---

## Generating the Excel Report

Use the bundled script:

```python
from scripts.excel_generator import generate_migration_report

generate_migration_report(
    optimization_results=results,  # List of 3 scenario results
    packages=packages,             # List of migration packages
    config=config,                 # Optimization configuration
    output_path="migration_roadmap_report.xlsx"
)
```

Or from command line:
```bash
python scripts/excel_generator.py results.json packages.json config.json output.xlsx
```

Or generate a sample workbook:
```bash
python generate_sample_roadmap.py
```

---

## Interpreting Results for Stakeholders

### For Executives
> "We analysed 25 packages across 3 scenarios. The Balanced approach completes in 45 months with 40% strategic coverage. The Effort & Cost Model shows a $2.1M total investment. We recommend this as it balances speed with long-term maintainability."

### For Project Managers
> "The Risk Assessment identifies 4 Critical packages requiring immediate mitigation plans. The Dependency Analysis shows the Integration Gateway as the highest-impact item — any delay propagates to 5 downstream packages."

### For Technical Leads
> "Strategic mode is used for all high-criticality packages. The Assumptions sheet lets you model different FTE rates and mode multipliers to optimise cost/duration trade-offs."

---

## Additional Outputs (Optional)

If requested, the optimizer can also generate:

### CSV Exports
- `scenario_comparison.csv` — Metrics table
- `{scenario}_schedule.csv` — Per-scenario schedules

### Markdown Reports
- Executive summary in markdown format
- Risk assessment report
