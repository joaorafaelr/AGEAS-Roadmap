# Roadmap Optimizer Skill - Comprehensive Review

Generated: March 16, 2026

This document identifies all issues, inconsistencies, and improvement opportunities across the skill's documentation and scripts.

---

## Issue Categories

- 🔴 **CRITICAL**: Breaks functionality or creates confusion
- 🟠 **IMPORTANT**: Affects reusability or accuracy
- 🟡 **MINOR**: Cosmetic or nice-to-have improvements

---

## File: SKILL.md

### 🟠 Issue 1.1: SAS-specific terminology in examples
**Location**: Lines 156-173 (Example Usage Patterns)
**Problem**: All examples reference "SAS programs" and "SAS-to-Databricks"
**Fix**: Add more generic examples or make SAS one of several example patterns

### 🟡 Issue 1.2: xlsx skill mentioned but should be avoided
**Location**: Line 54 mentions excel-generator subagent, but line 79 doesn't explicitly warn against xlsx skill
**Problem**: User might invoke xlsx skill instead of the bundled Python script
**Fix**: Add explicit warning: "Do NOT use the xlsx skill - always use scripts/excel_generator.py"

### 🟠 Issue 1.3: Hardcoded "Polaris, DC Claims, EDM" references
**Location**: Lines 134-140 (Domain-Specific Features)
**Problem**: These are Ageas-specific future core systems
**Fix**: Make these configurable via the config.json with generic terminology

---

## File: references/1-inputs.md

### 🟢 GOOD: Already generic
This file is well-written and mostly technology-agnostic. Examples cover multiple migration types.

### 🟡 Issue 2.1: Hardcoded domain enum
**Location**: Line 103 - domain enum is "customer, product, claims, finance, operations"
**Problem**: Not aligned with actual data (Claims, Entities, Policies)
**Fix**: Remove hardcoded enum, explain domains are user-configurable

### 🟡 Issue 2.2: System deadline examples use specific names
**Location**: Lines 200-210 (System Decommissioning Dates)
**Problem**: Examples mention "Legacy Mainframe", "Old CRM" - good, but the constraint formula references hardcoded systems
**Fix**: Clarify these are examples; actual systems come from config

---

## File: references/2-criteria.md

### 🟠 Issue 3.1: SAS license reference
**Location**: Line 144 - "Choose this if: SAS licenses are expiring"
**Problem**: SAS-specific
**Fix**: Change to "Choose this if: Source platform licenses are expiring or there's pressure to decommission the legacy system quickly"

### 🟠 Issue 3.2: ODL references
**Location**: Lines 48-50 reference "ODL" without explanation
**Problem**: ODL is Ageas-specific (Operational Data Layer?)
**Fix**: Either explain what ODL means generically or remove the reference

### 🟡 Issue 3.3: Hardcoded 438 hours in cost formulas
**Location**: Lines 65-69
**Problem**: Bridge-from-Legacy cost of 438 hours is Ageas-specific
**Fix**: Reference configuration instead - these should be parameters in config.json

---

## File: references/3-hard-constraints.md

### 🔴 Issue 4.1: Ageas-specific system deadlines table
**Location**: Lines 158-164
**Problem**: Table explicitly lists CCS, DC Policy, Tecnisys, Cogen with specific dates
**Fix**: Move this to an "Example Configuration" section and clarify these come from config.json

### 🟠 Issue 4.2: Domain-specific rules tables
**Location**: Lines 222-250 (Claims Domain, Entities Domain, Policies Domain)
**Problem**: Entire sections are Ageas-specific business rules (NR34/NR35/NR36 regulatory references)
**Fix**: Make these examples and add explanation that domain-specific rules come from configuration

### 🟠 Issue 4.3: Strategic Approach Prerequisites hardcoded
**Location**: Lines 197-215
**Problem**: "future_core_available" references Polaris, DC_Claims, EDM specifically
**Fix**: Generalize to "target_system_available" and make systems configurable

---

## File: references/4-soft-constraints.md

### 🟢 GOOD: Mostly well-structured

### 🟠 Issue 5.1: "ODL replica" terminology
**Location**: Line 49
**Problem**: ODL-specific
**Fix**: Generalize to "target system replica" or "staging environment"

### 🟡 Issue 5.2: Hardcoded base hours
**Location**: Lines 243-293 (Approach Cost Profiles)
**Problem**: 438 hours and 150 hours are hardcoded
**Fix**: Reference config.mode_parameters instead, show these as example values

### 🟠 Issue 5.3: Future core decision rules
**Location**: Lines 315-336
**Problem**: Decision logic hardcodes "Polaris OR DC_Claims OR EDM"
**Fix**: Abstract to "cluster_belongs_to_future_core" with configurable list

---

## File: references/5-optimization.md

### 🟢 GOOD: This file is well-written and mostly generic
The solver explanation is clear and technology-agnostic.

### 🟡 Issue 6.1: Example output references "SAS"
**Location**: Line 266
**Problem**: Minor - example mentions SAS-specific context
**Fix**: Make example generic

---

## File: references/6-outputs.md

### 🟢 GOOD: Excellent documentation of Excel structure
The 12-sheet structure is well-defined.

### 🟡 Issue 7.1: Script reference could be clearer
**Location**: Lines 259-283
**Problem**: Shows both API usage and CLI usage but doesn't emphasize "use this, not xlsx skill"
**Fix**: Add explicit note at top: "IMPORTANT: Always use scripts/excel_generator.py. Do not use the xlsx skill."

---

## File: references/7-mathematical-formulation.md

### 🟢 GOOD: Mathematically sound and clear

### 🟡 Issue 8.1: Hardcoded system deadlines in constraint section
**Location**: Lines 217-220
**Problem**: Lists CCS, DC Policy, Tecnisys/Cogen with specific month numbers
**Fix**: Show as examples from configuration

### 🟠 Issue 8.2: Future Core Systems table
**Location**: Lines 79-84
**Problem**: Hardcodes Polaris, DC Claims, EDM
**Fix**: Make configurable, show as example

---

## File: references/8-workflow-orchestration.md

### 🟢 GOOD: Excellent workflow documentation
Clear step-by-step instructions with subagent usage.

### 🟠 Issue 9.1: Critical Excel generation instructions
**Location**: Lines 207-243
**Problem**: Says "CRITICAL" but could be stronger about NOT using xlsx skill
**Fix**: Add explicit warning: "WARNING: Never use the xlsx skill. Always spawn the excel-generator subagent which uses scripts/excel_generator.py"

---

## File: references/schemas.md

### 🟠 Issue 10.1: Domain enum is outdated
**Location**: Lines 20-21
**Problem**: Domain enum is ["customer", "product", "claims", "finance", "operations"] but actual data uses ["Claims", "Entities", "Policies"]
**Fix**: Remove hardcoded enum, make domains user-configurable with case-insensitive matching

### 🟡 Issue 10.2: Mode names inconsistent
**Location**: Lines 117, 325
**Problem**: Uses "build_to_legacy" but other files sometimes reference "legacy_replication"
**Fix**: Standardize on snake_case names throughout: build_to_legacy, bridge_to_model, strategic

---

## File: agents/data-loader.md

### 🟠 Issue 11.1: Hardcoded source system table
**Location**: Lines 64-68
**Problem**: Lists CCS, DC Policy, Tecnisys, Cogen specifically
**Fix**: Reference configuration for system deadlines

### 🟠 Issue 11.2: Future core tagging hardcoded
**Location**: Lines 70-75
**Problem**: Lists Polaris, DC Claims, EDM explicitly
**Fix**: Reference config.future_core_systems

---

## File: agents/package-aggregator.md

### 🟠 Issue 12.1: Domain-specific rules hardcoded
**Location**: Lines 35-37
**Problem**: Claims atomic units, Entities no-split, Policies life/non-life split are Ageas-specific
**Fix**: Reference config.business_rules for domain-specific packaging rules

### 🟠 Issue 12.2: Foundational clusters hardcoded
**Location**: Lines 40-47
**Problem**: Entity Dimensions, Policy Core, Claims Core are Ageas-specific
**Fix**: Reference config.business_rules.foundational_clusters

---

## File: agents/scenario-optimizer.md

### 🟢 GOOD: Well-structured parallel execution guide

### 🟡 Issue 13.1: Minor code example references could be clearer
**Location**: Lines 104-120
**Problem**: Shows concurrent limit code but could reference configuration
**Fix**: Add note that limits come from config.concurrent_limits

---

## File: agents/excel-generator.md

### 🔴 Issue 14.1: Missing explicit warning against xlsx skill
**Location**: Throughout
**Problem**: Doesn't explicitly state "Do NOT use xlsx skill"
**Fix**: Add prominent warning at top: "CRITICAL: This subagent MUST use scripts/excel_generator.py. Never invoke the xlsx skill."

---

## File: scripts/excel_generator.py

### 🟢 GOOD: Comprehensive, well-structured Python script
The script already handles the full 12-sheet financial model.

### 🟡 Issue 15.1: Missing CLI usage documentation
**Problem**: Has main() function but command-line arguments could be clearer
**Fix**: Add argparse and usage documentation

---

## File: scripts/generate_excel_report.py

### 🟠 Issue 16.1: Duplicate/competing Excel generation script
**Problem**: This is a simpler 6-sheet version that could confuse which to use
**Fix**: Either remove this file, or rename it to "generate_simple_report.py" and add deprecation notice

---

## File: data/jobs_input.json

### 🟢 GOOD: Well-structured job data

### 🟠 Issue 17.1: Not integrated with estimation formulas
**Problem**: Real job metrics (steps, transformations, source columns) aren't used to derive effort
**Current**: effort_days appears to be manually estimated (720 days for 6 jobs = 120 days/job)
**Fix**: Add documentation explaining the effort estimation methodology and how to derive from job metrics

---

## File: data/enhanced_config.json

### 🟢 GOOD: Well-structured configuration

### 🟡 Issue 18.1: Empty domain_clusters and analytical_models
**Problem**: These are empty objects that should be populated
**Fix**: Either populate or remove if not used

---

## Summary Statistics

| Category | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟠 Important | 16 |
| 🟡 Minor | 10 |
| 🟢 Good (no changes) | 8 |
| **Total Issues** | **28** |

---

## Recommended Fix Order

### Phase 1: Critical Fixes (Do First)
1. Add explicit xlsx skill warnings to SKILL.md, 8-workflow-orchestration.md, and excel-generator.md
2. Fix schemas.md domain enum

### Phase 2: Reusability Improvements (Core Value)
3. Abstract Ageas-specific system names (CCS, Polaris, etc.) to configuration references
4. Generalize domain-specific rules to use config.business_rules
5. Abstract future core systems to config.future_core_systems
6. Remove ODL-specific terminology or explain generically

### Phase 3: Technical Grounding
7. Document how effort estimations connect to job metrics
8. Add reference to data/ folder for grounding
9. Ensure schemas reflect actual job structure

### Phase 4: Consistency & Polish
10. Standardize mode names (snake_case throughout)
11. Update examples to be more generic
12. Clean up duplicate Excel script or clarify which to use
