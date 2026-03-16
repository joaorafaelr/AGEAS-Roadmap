#!/usr/bin/env python3
"""
MRCPSP Optimizer
Multi-Mode Resource-Constrained Project Scheduling Problem solver for migration roadmaps.
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

@dataclass
class OptimizationResult:
    scenario_name: str
    total_duration_months: int
    packages_by_mode: Dict[str, int]
    resource_utilization: float
    technical_debt_score: float
    strategic_coverage: float
    schedule: List[Dict]
    objective_value: float

class MRCSPSolver:
    def __init__(self, packages_file: str, config_file: str):
        self.packages = self._load_packages(packages_file)
        self.config = self._load_config(config_file)
        self.model = None
        self.solver = None

    def _load_packages(self, packages_file: str) -> List[Dict]:
        """Load migration packages from JSON file."""
        with open(packages_file) as f:
            return json.load(f)

    def _load_config(self, config_file: str) -> Dict:
        """Load optimization configuration."""
        with open(config_file) as f:
            return json.load(f)

    def create_model(self, scenario_weights: Dict[str, float]) -> cp_model.CpModel:
        """Create CP-SAT optimization model."""
        model = cp_model.CpModel()

        # Time horizon
        horizon = self.config['migration_horizon_months']

        # Migration modes
        modes = ['build_to_legacy', 'bridge_to_model', 'strategic']

        # Decision variables
        self.start_vars = {}
        self.end_vars = {}
        self.mode_vars = {}
        self.duration_vars = {}

        # Package variables
        for i, package in enumerate(self.packages):
            package_id = package['package_id']

            # Mode selection (exactly one mode per package)
            self.mode_vars[package_id] = {}
            mode_choices = []

            for mode in modes:
                var = model.NewBoolVar(f'mode_{package_id}_{mode}')
                self.mode_vars[package_id][mode] = var
                mode_choices.append(var)

            # Exactly one mode per package
            model.Add(sum(mode_choices) == 1)

            # Start and end times (conditional on mode)
            self.start_vars[package_id] = model.NewIntVar(0, horizon, f'start_{package_id}')
            self.end_vars[package_id] = model.NewIntVar(1, horizon, f'end_{package_id}')

            # Duration based on mode selection
            self.duration_vars[package_id] = {}
            for mode in modes:
                duration = self._get_mode_duration(package, mode)
                self.duration_vars[package_id][mode] = duration

                # If mode is selected, enforce duration constraint
                model.Add(
                    self.end_vars[package_id] ==
                    self.start_vars[package_id] + duration
                ).OnlyEnforceIf(self.mode_vars[package_id][mode])

        # Precedence constraints
        self._add_precedence_constraints(model)

        # Resource constraints
        self._add_resource_constraints(model, horizon)

        # Note: ODL constraint removed - Strategic mode now uses replica approach
        # and can start at any time. When ODL is ready, packages will be updated.
        # Legacy constraint call commented out:
        # self._add_odl_constraints(model)

        # Objective function
        self._add_objective(model, scenario_weights)

        self.model = model
        return model

    def _get_mode_duration(self, package: Dict, mode: str) -> int:
        """Calculate duration in months for a package in a given mode."""
        base_effort = package['total_effort_days']
        complexity = package['complexity_score']

        # Mode-specific multipliers
        mode_factors = {
            'build_to_legacy': 0.8,  # Fastest but creates tech debt
            'bridge_to_model': 1.0,  # Baseline duration
            'strategic': 1.3        # Longer but cleanest result
        }

        # Convert days to months (assuming 20 working days per month)
        duration_months = max(1, int((base_effort * mode_factors[mode] * complexity) / 20))

        return duration_months

    def _add_precedence_constraints(self, model: cp_model.CpModel) -> None:
        """Add precedence constraints based on package dependencies."""
        package_lookup = {p['package_id']: p for p in self.packages}

        for package in self.packages:
            package_id = package['package_id']

            # This package cannot start until all upstream packages are complete
            for upstream_job in package['upstream_packages']:
                # Find package containing upstream job
                upstream_package = None
                for p in self.packages:
                    if upstream_job in p.get('job_ids', []):
                        upstream_package = p['package_id']
                        break

                if upstream_package and upstream_package != package_id:
                    model.Add(
                        self.start_vars[package_id] >= self.end_vars[upstream_package]
                    )

    def _add_resource_constraints(self, model: cp_model.CpModel, horizon: int) -> None:
        """Add resource capacity constraints."""
        team_capacity = self.config['team_capacity']  # 6 people (2 teams of 3)

        # For each time period, total resource consumption <= capacity
        for month in range(horizon):
            month_demand = []

            for package in self.packages:
                package_id = package['package_id']

                # Calculate resource demand for this package in this month
                for mode in ['build_to_legacy', 'bridge_to_model', 'strategic']:
                    # Resource consumption if package is active in this month with this mode
                    resource_demand = self._get_mode_resource_demand(package, mode)

                    # Boolean: is this package active in this month with this mode?
                    is_active = model.NewBoolVar(f'active_{package_id}_{mode}_{month}')

                    # Package is active if it's started and not finished
                    model.Add(self.start_vars[package_id] <= month).OnlyEnforceIf(is_active)
                    model.Add(self.end_vars[package_id] > month).OnlyEnforceIf(is_active)
                    model.Add(self.mode_vars[package_id][mode] == 1).OnlyEnforceIf(is_active)

                    # If not active, then constraints are not enforced
                    model.Add(self.start_vars[package_id] > month).OnlyEnforceIf(is_active.Not())
                    model.AddBoolOr([
                        self.end_vars[package_id].Not() > month,
                        self.mode_vars[package_id][mode].Not()
                    ]).OnlyEnforceIf(is_active.Not())

                    month_demand.append(resource_demand * is_active)

            # Total demand in this month <= capacity
            if month_demand:
                model.Add(sum(month_demand) <= team_capacity)

    def _get_mode_resource_demand(self, package: Dict, mode: str) -> int:
        """Calculate resource demand (number of people) for package in given mode."""
        # Simplified: assume each package needs 1-3 people based on complexity
        complexity = package['complexity_score']

        if complexity <= 2:
            return 1
        elif complexity <= 4:
            return 2
        else:
            return 3

    def _add_odl_constraints(self, model: cp_model.CpModel) -> None:
        """
        DEPRECATED: ODL dependency constraints no longer applied.

        Strategic mode now uses a replica-first approach:
        - Strategic packages can start at any time using the ODL replica
        - When ODL production is ready, packages are updated to use real ODL
        - This removes the previous blocking constraint

        Kept for reference in case constraint needs to be re-enabled.
        """
        # Original implementation (now disabled):
        # odl_completion_month = self.config.get('odl_completion_month', 18)
        # for package in self.packages:
        #     package_id = package['package_id']
        #     model.Add(
        #         self.start_vars[package_id] >= odl_completion_month
        #     ).OnlyEnforceIf(self.mode_vars[package_id]['strategic'])
        pass  # No constraints applied

    def _add_objective(self, model: cp_model.CpModel, weights: Dict[str, float]) -> None:
        """Add weighted objective function."""
        objective_terms = []

        # 1. Minimize total project duration
        if 'minimize_duration' in weights:
            max_end = model.NewIntVar(0, self.config['migration_horizon_months'], 'max_end')
            for package in self.packages:
                model.AddMaxEquality(max_end, [self.end_vars[p['package_id']] for p in self.packages])
            objective_terms.append(weights['minimize_duration'] * max_end)

        # 2. Maximize strategic coverage
        if 'maximize_strategic' in weights:
            strategic_packages = []
            for package in self.packages:
                package_id = package['package_id']
                business_value = int(package['business_value'] * 100)
                strategic_packages.append(
                    business_value * self.mode_vars[package_id]['strategic']
                )
            objective_terms.append(-weights['maximize_strategic'] * sum(strategic_packages))

        # 3. Minimize technical debt
        if 'minimize_tech_debt' in weights:
            tech_debt_terms = []
            for package in self.packages:
                package_id = package['package_id']
                debt_penalty = int(package['complexity_score'] * 10)

                # Build-to-legacy creates most debt
                tech_debt_terms.append(
                    debt_penalty * 2 * self.mode_vars[package_id]['build_to_legacy']
                )
                # Bridge creates some debt
                tech_debt_terms.append(
                    debt_penalty * 1 * self.mode_vars[package_id]['bridge_to_model']
                )
                # Strategic creates no debt (penalty = 0)

            objective_terms.append(weights['minimize_tech_debt'] * sum(tech_debt_terms))

        # Set objective
        if objective_terms:
            model.Minimize(sum(objective_terms))

    def solve_scenario(self, scenario_name: str, weights: Dict[str, float]) -> OptimizationResult:
        """Solve optimization for a specific scenario."""
        print(f"Solving scenario: {scenario_name}")

        # Create model
        model = self.create_model(weights)

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300  # 5 minute timeout

        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return self._extract_solution(solver, scenario_name)
        else:
            raise Exception(f"No solution found for scenario {scenario_name}. Status: {status}")

    def _extract_solution(self, solver: cp_model.CpSolver, scenario_name: str) -> OptimizationResult:
        """Extract solution from solver."""
        schedule = []
        packages_by_mode = {'build_to_legacy': 0, 'bridge_to_model': 0, 'strategic': 0}
        total_effort = 0
        strategic_effort = 0
        tech_debt_score = 0

        for package in self.packages:
            package_id = package['package_id']

            start_month = solver.Value(self.start_vars[package_id])
            end_month = solver.Value(self.end_vars[package_id])

            # Determine selected mode
            selected_mode = None
            for mode in ['build_to_legacy', 'bridge_to_model', 'strategic']:
                if solver.Value(self.mode_vars[package_id][mode]) == 1:
                    selected_mode = mode
                    packages_by_mode[mode] += 1
                    break

            effort = package['total_effort_days']
            total_effort += effort

            if selected_mode == 'strategic':
                strategic_effort += effort

            # Calculate tech debt contribution
            if selected_mode == 'build_to_legacy':
                tech_debt_score += package['complexity_score'] * 2
            elif selected_mode == 'bridge_to_model':
                tech_debt_score += package['complexity_score'] * 1

            schedule.append({
                'package_id': package_id,
                'package_name': package['name'],
                'domain': package['domain'],
                'start_month': start_month,
                'end_month': end_month,
                'duration_months': end_month - start_month,
                'selected_mode': selected_mode,
                'effort_days': effort,
                'business_value': package['business_value']
            })

        # Calculate metrics
        total_duration = max(item['end_month'] for item in schedule)
        strategic_coverage = strategic_effort / total_effort if total_effort > 0 else 0

        # Simplified resource utilization calculation
        resource_utilization = 0.75  # Placeholder - would need detailed calculation

        return OptimizationResult(
            scenario_name=scenario_name,
            total_duration_months=total_duration,
            packages_by_mode=packages_by_mode,
            resource_utilization=resource_utilization,
            technical_debt_score=tech_debt_score,
            strategic_coverage=strategic_coverage,
            schedule=schedule,
            objective_value=solver.ObjectiveValue() if solver.ObjectiveValue() else 0
        )

    def run_all_scenarios(self) -> List[OptimizationResult]:
        """Run optimization for all predefined scenarios."""
        scenarios = {
            'Fast Exit': {
                'minimize_duration': 0.6,
                'maximize_strategic': 0.1,
                'minimize_tech_debt': 0.3
            },
            'Balanced': {
                'minimize_duration': 0.3,
                'maximize_strategic': 0.4,
                'minimize_tech_debt': 0.3
            },
            'Target First': {
                'minimize_duration': 0.2,
                'maximize_strategic': 0.6,
                'minimize_tech_debt': 0.2
            }
        }

        results = []
        for scenario_name, weights in scenarios.items():
            try:
                result = self.solve_scenario(scenario_name, weights)
                results.append(result)
            except Exception as e:
                print(f"Failed to solve {scenario_name}: {e}")

        return results

    def generate_comparison_report(self, results: List[OptimizationResult], output_dir: str) -> None:
        """Generate comparison report and visualizations."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Create comparison table
        comparison_data = []
        for result in results:
            comparison_data.append({
                'Scenario': result.scenario_name,
                'Duration (months)': result.total_duration_months,
                'Strategic Coverage (%)': f"{result.strategic_coverage:.1%}",
                'Tech Debt Score': f"{result.technical_debt_score:.1f}",
                'Resource Utilization (%)': f"{result.resource_utilization:.1%}",
                'Build-to-Legacy': result.packages_by_mode['build_to_legacy'],
                'Bridge-to-Model': result.packages_by_mode['bridge_to_model'],
                'Strategic': result.packages_by_mode['strategic']
            })

        df_comparison = pd.DataFrame(comparison_data)
        df_comparison.to_csv(output_path / 'scenario_comparison.csv', index=False)

        # Generate visualizations
        self._create_gantt_charts(results, output_path)
        self._create_comparison_charts(results, output_path)

        # Export detailed schedules
        for result in results:
            schedule_df = pd.DataFrame(result.schedule)
            schedule_df.to_csv(output_path / f'{result.scenario_name.lower().replace(" ", "_")}_schedule.csv', index=False)

        print(f"Reports generated in {output_path}")

    def _create_gantt_charts(self, results: List[OptimizationResult], output_path: Path) -> None:
        """Create Gantt charts for each scenario."""
        for result in results:
            fig, ax = plt.subplots(figsize=(15, 10))

            # Sort by start month
            schedule = sorted(result.schedule, key=lambda x: x['start_month'])

            # Color map for modes
            mode_colors = {
                'build_to_legacy': '#ff7f7f',
                'bridge_to_model': '#7f7fff',
                'strategic': '#7fff7f'
            }

            y_pos = range(len(schedule))

            for i, task in enumerate(schedule):
                start = task['start_month']
                duration = task['duration_months']
                mode = task['selected_mode']

                ax.barh(i, duration, left=start, height=0.8,
                       color=mode_colors[mode], alpha=0.7,
                       label=mode if mode not in [t.get_text() for t in ax.get_legend().get_texts() if ax.get_legend()] else "")

                # Add package name
                ax.text(start + duration/2, i, task['package_name'][:20],
                       ha='center', va='center', fontsize=8)

            ax.set_yticks(y_pos)
            ax.set_yticklabels([t['package_name'][:30] for t in schedule])
            ax.set_xlabel('Month')
            ax.set_title(f'Migration Schedule - {result.scenario_name}')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_path / f'{result.scenario_name.lower().replace(" ", "_")}_gantt.png', dpi=300)
            plt.close()

    def _create_comparison_charts(self, results: List[OptimizationResult], output_path: Path) -> None:
        """Create comparison charts across scenarios."""
        # Metrics comparison
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        scenarios = [r.scenario_name for r in results]

        # Duration comparison
        durations = [r.total_duration_months for r in results]
        ax1.bar(scenarios, durations, color=['#ff9999', '#66b3ff', '#99ff99'])
        ax1.set_title('Total Duration (Months)')
        ax1.set_ylabel('Months')

        # Strategic coverage
        strategic_coverage = [r.strategic_coverage * 100 for r in results]
        ax2.bar(scenarios, strategic_coverage, color=['#ff9999', '#66b3ff', '#99ff99'])
        ax2.set_title('Strategic Coverage (%)')
        ax2.set_ylabel('Percentage')

        # Tech debt score
        tech_debt = [r.technical_debt_score for r in results]
        ax3.bar(scenarios, tech_debt, color=['#ff9999', '#66b3ff', '#99ff99'])
        ax3.set_title('Technical Debt Score')
        ax3.set_ylabel('Score')

        # Mode distribution
        modes_data = []
        for result in results:
            modes_data.append([
                result.packages_by_mode['build_to_legacy'],
                result.packages_by_mode['bridge_to_model'],
                result.packages_by_mode['strategic']
            ])

        modes_df = pd.DataFrame(modes_data, columns=['Build-to-Legacy', 'Bridge-to-Model', 'Strategic'],
                               index=scenarios)
        modes_df.plot(kind='bar', stacked=True, ax=ax4, color=['#ff7f7f', '#7f7fff', '#7fff7f'])
        ax4.set_title('Package Distribution by Mode')
        ax4.set_ylabel('Number of Packages')
        ax4.legend(title='Migration Mode')

        plt.tight_layout()
        plt.savefig(output_path / 'scenario_comparison.png', dpi=300)
        plt.close()

def main():
    import sys

    if len(sys.argv) < 4:
        print("Usage: python mrcpsp_optimizer.py <packages_file> <config_file> <output_dir>")
        sys.exit(1)

    packages_file = sys.argv[1]
    config_file = sys.argv[2]
    output_dir = sys.argv[3]

    # Create solver
    solver = MRCSPSolver(packages_file, config_file)

    # Run all scenarios
    print("Running optimization scenarios...")
    results = solver.run_all_scenarios()

    # Generate reports
    print("Generating reports...")
    solver.generate_comparison_report(results, output_dir)

    print(f"Optimization complete. Results saved to {output_dir}")

if __name__ == "__main__":
    main()