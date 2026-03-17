# Subagent: Excel Generator

Use this prompt when spawning a subagent to generate the final Excel report.

---

> ⚠️ **CRITICAL: DO NOT USE THE XLSX SKILL**
>
> This subagent MUST use `scripts/excel_generator.py` to generate the Excel report.
> - **NEVER invoke the xlsx skill** — it cannot produce the comprehensive 12-sheet financial-model workbook
> - **ALWAYS use the bundled Python script** which creates professional outputs with formulas, charts, and conditional formatting
> - The xlsx skill produces simple spreadsheets without the financial-model conventions stakeholders expect

---

## Prompt Template

```
You are a report generation agent for the roadmap optimizer.

## Your Task
Generate a professional, formula-driven Excel workbook (12 sheets) with all optimization results.

**CRITICAL**:
- You MUST use scripts/excel_generator.py to generate the report
- DO NOT use the xlsx skill — it cannot produce the required financial-model workbook
- This MUST be a beautiful, detailed, modern Excel workbook using the comprehensive 12-sheet design

The workbook follows financial-model conventions:
  - Blue font = editable inputs (Assumptions sheet)
  - Black font = formulas
  - All derived values use Excel formulas that recalculate automatically
  - Named ranges for key assumption cells
  - Excel Tables with structured references for data sheets
  - Beautiful charts, conditional formatting, modern color schemes
  - Professional visual design throughout

## Inputs
- Packages: {WORKSPACE}/intermediate/packages.json
- Results:
  - {WORKSPACE}/results/fast_exit_result.json
  - {WORKSPACE}/results/balanced_result.json
  - {WORKSPACE}/results/target_first_result.json
- Configuration: {CONFIG_PATH}
- Output: {WORKSPACE}/output/migration_roadmap_report.xlsx

## Execution

Use the bundled script:

```python
from scripts.excel_generator import generate_migration_report
import json

# Load data
with open('packages.json') as f:
    packages = json.load(f)

results = []
for scenario in ['fast_exit', 'balanced', 'target_first']:
    with open(f'{scenario}_result.json') as f:
        results.append(json.load(f))

with open('config.json') as f:
    config = json.load(f)

# Generate 12-sheet financial-model report
generate_migration_report(
    optimization_results=results,
    packages=packages,
    config=config,
    output_path='migration_roadmap_report.xlsx'
)
```

## Workbook Structure (12 Sheets)

### Sheet 1: Assumptions
The cornerstone — every tunable parameter lives here.

Layout:
```
Row 1:  [Title] "Assumptions & Parameters"
Row 2:  [Subtitle] "Blue cells are editable inputs…"
Row 4:  [Section] General Parameters
        - Migration Horizon (months)    [60]     ← blue font, yellow bg
        - Team Capacity                 [6]
        - FTE Daily Cost Rate ($)       [850]
        - Working Days per Month        [20]
        - Risk Buffer Factor            [0.25]
        - Dependency Criticality Threshold  [3]
        - Complexity Criticality Threshold  [3.5]

Row 12: [Section] Mode Parameters (Excel Table: ModeTable)
        | Mode             | Duration Mult | Tech Debt Pen | Resource Eff | Cost Mult |
        | Build-to-Legacy  | 0.70          | 3.00          | 1.20         | 0.80      |
        | Bridge-to-Model  | 1.00          | 1.50          | 1.00         | 1.00      |
        | Strategic        | 1.40          | 0.50          | 0.80         | 1.30      |

Row 18: [Section] Domain Priority & Earliest Start (Excel Table: DomainTable)
Row 25: [Section] Scenario Objective Weights (Excel Table: ScenarioWeightsTable)
Row 32: [Section] Risk Assessment Weights
```

Named ranges: `horizon_months`, `team_capacity`, `fte_daily_rate`, `working_days_month`,
`risk_buffer_factor`, `risk_w_complexity`, `risk_w_dependency`, `risk_w_bv`, `risk_w_volume`

### Sheet 2: Package_Data
Raw package inventory as an Excel Table (`PackageData`).

| Package_ID | Name | Domain | Job_Count | Effort_Days | Complexity | Business_Value | Risk_Score | Upstream_Count | Downstream_Count |

Features:
- Structured Excel Table with auto-filter
- Data bars on Complexity
- Color-scale on Risk Score (green → red)
- Named ranges: `pkg_ids`, `pkg_effort`, `pkg_complexity`, `pkg_bv`, `pkg_risk`

### Sheets 3–5: Schedule_FastExit / Schedule_Balanced / Schedule_TargetFirst
Per-scenario schedules as Excel Tables.

| Package_ID | Name | Domain | Start_Month | End_Month | Duration | Mode | Effort_Days | Business_Value |

Features:
- Duration column = formula `=End_Month - Start_Month`
- Mode column with conditional formatting rules (3 rules: BtL red, BtM blue, Strategic green)
- Auto-filter, frozen headers

### Sheet 6: Executive_Summary
All KPIs are formulas pulling from schedule and package sheets.

```
Row 1:   [Title] "Migration Roadmap — Executive Summary"
Row 6–7: [KPI Cards]
  - Total Packages: =COUNTA(Package_Data!A:A)
  - Scenarios: 3
  - Horizon: =Assumptions!horizon_months
  - Team Capacity: =Assumptions!team_capacity

Row 10+: [Scenario Comparison Table]
  - Duration: =MAX(Schedule_X!End_Month)
  - Strategic %: =COUNTIF(Schedule_X!Mode,"Strategic")/COUNTA(Schedule_X!ID)
  - Mode counts: =COUNTIF(Schedule_X!Mode,"…")
  - Total Effort: =SUM(Schedule_X!Effort)

Row 20+: [Recommendations] Auto-generated text
```

### Sheet 7: Scenario_Comparison
Detailed metrics — all formulas.
- Side-by-side metrics table with "Best ✓" column
- Mode distribution chart data table
- Stacked bar chart linked to formula cells

### Sheet 8: Timeline_Gantt
Visual Gantt using cell fills.
- Package names in column A, M0…M60 in columns C+
- Mode-coloured fills for active months
- Legend row

### Sheet 9: Effort_Cost_Model (NEW)
Full cost analysis with formulas:
- Scenario Cost Summary table: Total Effort, Total Cost, Duration, Cost/Month
- Total Cost = Effort × FTE_Daily_Rate (from Assumptions)
- Monthly Burn Rate table (M0–M35) per scenario
  - =SUMPRODUCT of active packages' effort weighted by daily rate
- Line chart: monthly burn rate by scenario

### Sheet 10: Risk_Assessment (NEW)
Risk scoring with weighted formula model:
- Per-package columns from Package_Data via formulas
- Weighted Risk = (Complexity/5×W1 + Deps/10×W2 + (10-BV)/10×W3 + Jobs/50×W4)
- Risk Category: =IF(risk>0.7,"Critical", IF(…))
- Risk-Adjusted Duration: =Duration × (1 + Risk × buffer_factor)
- Heat-map conditional formatting on risk score
- Category conditional formatting (Critical=red, High=amber, Medium=green, Low=cyan)
- Summary: count + % per category, average risk score
- Pie chart for risk distribution

### Sheet 11: Dependency_Analysis (NEW)
Dependency chain analysis:
- Per-package: Upstream, Downstream, Total, Fan-Out Score, Critical Path, Impact Score
- Critical Path = IF(Downstream ≥ threshold AND Complexity ≥ threshold)
- Impact Score = Downstream × Business_Value / 10
- Data bars on Fan-Out, colour scale on Impact
- Domain interconnection matrix
- Summary statistics: total critical items, max fan-out, avg deps, highest-impact package

### Sheet 12: Data_Appendix
Configuration recap (formula references to Assumptions), domain breakdown (COUNTIF/SUMIF),
mode distribution per scenario, report metadata.

## Styling Standards

- **Font**: Calibri 11pt throughout
- **Blue font** (0,0,255): all editable inputs in Assumptions
- **Black font**: all formula cells
- **Yellow background**: key assumption cells
- **Number formats**: `#,##0` integers, `$#,##0` currency, `0.0%` percentages
- **Headers**: white text on dark background (#2E5A88)
- **Conditional formatting**: ColorScale, DataBar, CellIsRule for modes/risk
- **Named ranges**: for all key assumption cells
- **Excel Tables**: structured tables with TableStyleMedium2/9

## Success Criteria
- Excel file opens without errors in Excel 365
- All 12 sheets present and populated
- Change an Assumptions value → downstream sheets recalculate
- No #REF!, #DIV/0!, or #NAME? errors
- Charts render and update with data changes
- Conditional formatting applies correctly
- Return: "Report generated: {path} (12 sheets, {M} packages)"
```

---

## Expected Duration
- 1–2 minutes
- Excel generation is I/O bound, not CPU bound
