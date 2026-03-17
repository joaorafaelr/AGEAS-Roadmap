#!/usr/bin/env python3
"""
Roadmap optimizer

A stronger CP-SAT implementation for the roadmap-optimizer skill:
- validates and normalizes package/config inputs
- models modes with optional intervals and cumulative resources
- applies the documented hard constraints as closely as the available inputs allow
- solves each scenario in exact staged passes rather than one loose weighted sum
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover - exercised indirectly in tests
    cp_model = None


CP_SAT_AVAILABLE = cp_model is not None

MODE_ORDER = ("build_to_legacy", "bridge_to_model", "strategic")
SCENARIO_FILES = {
    "Fast Exit": "fast_exit",
    "Balanced": "balanced",
    "Target-First": "target_first",
}
MODE_LABELS = {
    "build_to_legacy": "Build-to-Legacy",
    "bridge_to_model": "Bridge-to-Model",
    "strategic": "Strategic",
}
MODE_ALIASES = {
    "build_to_legacy": (
        "build_to_legacy",
        "legacy_replication",
        "lift_and_shift",
        "build_to_legacy_replication",
    ),
    "bridge_to_model": (
        "bridge_to_model",
        "bridge_approach",
        "bridge",
        "bridge_to_target",
    ),
    "strategic": (
        "strategic",
        "strategic_rewrite",
        "direct",
        "direct_target",
    ),
}
LEGACY_COMPLEXITY_MAP = {
    "low": 1.8,
    "medium": 3.0,
    "high": 4.8,
    "critical": 5.6,
}
DEFAULT_MODE_PARAMETERS = {
    "build_to_legacy": {
        "duration_multiplier": 0.8,
        "tech_debt_penalty": 2.0,
        "resource_efficiency": 1.0,
        "base_hours": 438,
        "cost_multiplier": 1.0,
        "strategic_value": 0.2,
        "future_migration_hours": 438,
    },
    "bridge_to_model": {
        "duration_multiplier": 1.0,
        "tech_debt_penalty": 1.0,
        "resource_efficiency": 0.9,
        "base_hours": 150,
        "cost_multiplier": 1.0,
        "strategic_value": 0.6,
        "future_migration_hours": 0,
    },
    "strategic": {
        "duration_multiplier": 1.3,
        "tech_debt_penalty": 0.0,
        "resource_efficiency": 0.8,
        "base_hours": 438,
        "cost_multiplier": 1.0,
        "strategic_value": 1.0,
        "future_migration_hours": 0,
    },
}
DEFAULT_SCENARIO_WEIGHTS = {
    "fast_exit": {
        "minimize_duration": 0.6,
        "maximize_strategic": 0.1,
        "minimize_tech_debt": 0.3,
    },
    "balanced": {
        "minimize_duration": 0.3,
        "maximize_strategic": 0.4,
        "minimize_tech_debt": 0.3,
    },
    "target_first": {
        "minimize_duration": 0.2,
        "maximize_strategic": 0.6,
        "minimize_tech_debt": 0.2,
    },
}
DEFAULT_RECOMMENDATION_WEIGHTS = {
    "duration": 0.35,
    "tech_debt": 0.25,
    "strategic_coverage": 0.25,
    "utilization_deviation": 0.10,
    "proof_penalty": 0.15,
}


class ValidationError(ValueError):
    """Raised when the package or config inputs are invalid."""


@dataclass
class StageOutcome:
    stage_name: str
    metric_key: str
    sense: str
    status: str
    target_value: int
    solve_time_seconds: float
    objective_value: float
    best_bound: Optional[float] = None


@dataclass
class OptimizationResult:
    scenario_name: str
    total_duration_months: int
    packages_by_mode: Dict[str, int]
    resource_utilization: float
    technical_debt_score: float
    strategic_coverage: float
    schedule: List[Dict[str, Any]]
    objective_value: float
    optimization_strategy: str = "staged_exact_cp_sat"
    objective_breakdown: Dict[str, Any] = field(default_factory=dict)
    solver_statistics: Dict[str, Any] = field(default_factory=dict)
    proof_status: str = "UNKNOWN"
    constraint_violations: List[Dict[str, str]] = field(default_factory=list)
    total_cost_score: float = 0.0
    risk_exposure_score: float = 0.0


@dataclass
class ModelContext:
    model: Any
    start_vars: Dict[str, Any]
    end_vars: Dict[str, Any]
    mode_vars: Dict[str, Dict[str, Any]]
    intervals: Dict[str, Dict[str, Any]]
    duration_by_mode: Dict[str, Dict[str, int]]
    demand_by_mode: Dict[str, Dict[str, int]]
    cost_by_mode: Dict[str, Dict[str, int]]
    debt_by_mode: Dict[str, Dict[str, int]]
    strategic_alignment_by_mode: Dict[str, Dict[str, int]]
    max_end_var: Any
    objective_terms: Dict[str, Any]
    bounds: Dict[str, int]
    earliest_start_penalties: Dict[str, Any]
    resolved_upstreams: Dict[str, List[str]]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(round(float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _status_name(status_code: int) -> str:
    if not CP_SAT_AVAILABLE:
        return "UNAVAILABLE"
    mapping = {
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.OPTIMAL: "OPTIMAL",
    }
    return mapping.get(status_code, str(status_code))


class MRCSPSolver:
    """Scenario-based roadmap optimizer backed by OR-Tools CP-SAT."""

    def __init__(self, packages_file: str, config_file: str):
        self.packages_file = packages_file
        self.config_file = config_file
        # Load both files once up-front so package normalization can reference
        # config values without re-reading the JSON file (fixes fragile ordering).
        raw_config = self._load_json(config_file)
        self.config = self._normalize_config(raw_config, config_file)
        self.packages = self._normalize_packages(
            self._load_json(packages_file), packages_file, raw_config
        )
        self.package_by_id = {package["package_id"]: package for package in self.packages}
        self.job_to_package = self._build_job_to_package_index(self.packages)
        self.foundational_package_ids = self._identify_foundational_packages()

    @staticmethod
    def _load_json(path: str) -> Any:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _normalize_packages(
        self, raw_packages: Any, source_name: str, raw_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not isinstance(raw_packages, list) or not raw_packages:
            raise ValidationError(
                f"Packages file '{source_name}' must contain a non-empty JSON array."
            )

        normalized = []
        for index, raw_package in enumerate(raw_packages):
            if not isinstance(raw_package, dict):
                raise ValidationError(f"Package entry {index} is not a JSON object.")

            package_id = str(raw_package.get("package_id") or f"package_{index + 1:03d}")
            name = str(raw_package.get("name") or package_id)
            domain = str(raw_package.get("domain") or "unknown")

            jobs = raw_package.get("jobs", [])
            job_ids = raw_package.get("job_ids")
            if not job_ids and isinstance(jobs, list):
                job_ids = [
                    str(job["job_id"])
                    for job in jobs
                    if isinstance(job, dict) and job.get("job_id")
                ]
            if not job_ids:
                raise ValidationError(
                    f"Package '{package_id}' is missing the required 'job_ids' field."
                )

            total_effort_days = _safe_float(raw_package.get("total_effort_days"))
            if total_effort_days <= 0 and isinstance(jobs, list):
                total_effort_days = sum(
                    _safe_float(job.get("estimated_effort_days"))
                    for job in jobs
                    if isinstance(job, dict)
                )
            if total_effort_days <= 0:
                raise ValidationError(
                    f"Package '{package_id}' must have a positive 'total_effort_days'."
                )

            complexity_score = raw_package.get("complexity_score")
            if complexity_score is None:
                complexity_score = self._derive_complexity_score(raw_package)
            complexity_score = _safe_float(complexity_score, 1.0)
            if complexity_score <= 0:
                raise ValidationError(
                    f"Package '{package_id}' must have a positive 'complexity_score'."
                )

            upstream_packages = raw_package.get("upstream_packages")
            if upstream_packages is None:
                upstream_packages = raw_package.get("dependencies", [])
            downstream_packages = raw_package.get("downstream_packages", [])

            business_value = raw_package.get("business_value")
            if business_value is None:
                # Check if the config provides domain-level business values
                domain_bv = self._domain_business_values_from_raw_config(raw_config)
                if str(domain).lower() in domain_bv:
                    base = domain_bv[str(domain).lower()]
                    size_bonus = min(0.18, len(job_ids) / 500.0)
                    business_value = _clamp(base + size_bonus, 0.0, 1.0)
                else:
                    business_value = self._derive_business_value(domain, len(job_ids))
            business_value = _clamp(_safe_float(business_value, 0.5), 0.0, 1.0)

            risk_score = raw_package.get("risk_score")
            if risk_score is None:
                risk_score = self._derive_risk_score(
                    total_effort_days, complexity_score, upstream_packages
                )
            risk_score = _clamp(_safe_float(risk_score, 0.25), 0.0, 1.0)

            source_systems = raw_package.get("source_systems")
            if source_systems is None:
                source_systems = self._collect_source_systems(raw_package)

            normalized.append(
                {
                    "package_id": package_id,
                    "name": name,
                    "domain": domain,
                    "job_ids": [str(job_id) for job_id in job_ids],
                    "job_count": _safe_int(raw_package.get("job_count"), len(job_ids)),
                    "total_effort_days": total_effort_days,
                    "complexity_score": complexity_score,
                    "upstream_packages": [str(item) for item in upstream_packages or []],
                    "downstream_packages": [str(item) for item in downstream_packages or []],
                    "upstream_count": _safe_int(
                        raw_package.get("upstream_count"),
                        len(upstream_packages or []),
                    ),
                    "downstream_count": _safe_int(
                        raw_package.get("downstream_count"),
                        len(downstream_packages or []),
                    ),
                    "centrality_score": _clamp(
                        _safe_float(raw_package.get("centrality_score"), 0.0), 0.0, 1.0
                    ),
                    "business_value": business_value,
                    "risk_score": risk_score,
                    "source_systems": [str(item) for item in source_systems],
                    "belongs_to_future_core": self._derive_future_core_flag(raw_package, domain, raw_config),
                    "deadline_month": self._extract_deadline_month(raw_package),
                    "assigned_team": raw_package.get("assigned_team"),
                }
            )

        return normalized

    def _normalize_config(self, raw_config: Any, source_name: str) -> Dict[str, Any]:
        if not isinstance(raw_config, dict) or not raw_config:
            raise ValidationError(
                f"Config file '{source_name}' must contain a JSON object with optimizer settings."
            )

        horizon = _safe_int(raw_config.get("migration_horizon_months"))
        capacity = _safe_int(raw_config.get("team_capacity"))
        if horizon <= 0:
            raise ValidationError("Config must define a positive 'migration_horizon_months'.")
        if capacity <= 0:
            raise ValidationError("Config must define a positive 'team_capacity'.")

        concurrent_limits = raw_config.get("concurrent_limits", {})
        business_rules = raw_config.get("business_rules", {})
        parallel_limits = business_rules.get("parallel_limits", {})

        max_strategic_parallel = _safe_int(
            concurrent_limits.get(
                "max_strategic_parallel",
                parallel_limits.get("strategic_clusters_max", 2),
            ),
            2,
        )
        max_total_parallel = _safe_int(
            concurrent_limits.get(
                "max_total_parallel",
                parallel_limits.get("total_active_max", 4),
            ),
            4,
        )

        normalized = {
            "migration_horizon_months": horizon,
            "team_capacity": capacity,
            "working_days_month": _safe_int(raw_config.get("working_days_month"), 20),
            "target_platform_ready_month": _safe_int(
                raw_config.get("target_platform_ready_month")
                or raw_config.get("odl_completion_month"),
                0,
            ),
            "solver": {
                "max_time_in_seconds": _safe_float(
                    raw_config.get("solver", {}).get("max_time_in_seconds"),
                    300.0,
                ),
                "num_search_workers": _safe_int(
                    raw_config.get("solver", {}).get("num_search_workers"),
                    8,
                ),
                "random_seed": _safe_int(
                    raw_config.get("solver", {}).get("random_seed"),
                    42,
                ),
            },
            "role_rates": {
                key: _safe_float(value)
                for key, value in raw_config.get("role_rates", {}).items()
            },
            "fte_daily_rate": _safe_float(raw_config.get("fte_daily_rate"), 1000.0),
            "future_core_systems": set(raw_config.get("future_core_systems", [])),
            "future_core_domains": set(
                raw_config.get("future_core_domains", [])
                or business_rules.get("strategic_approach_domains", [])
            ),
            "foundational_clusters": business_rules.get("foundational_clusters", {}),
            "concurrent_limits": {
                "max_strategic_parallel": max(1, max_strategic_parallel),
                "max_total_parallel": max(1, max_total_parallel),
            },
            "domain_constraints": self._normalize_domain_constraints(
                raw_config.get("domain_constraints", {})
            ),
            "mode_parameters": self._normalize_mode_parameters(raw_config),
            "system_deadlines": self._normalize_deadlines(raw_config),
            "optimization_weights": raw_config.get(
                "optimization_weights", DEFAULT_SCENARIO_WEIGHTS
            ),
            "unsupported_metrics": [],
            "recommendation_weights": raw_config.get(
                "recommendation_weights", DEFAULT_RECOMMENDATION_WEIGHTS
            ),
        }

        if not normalized["role_rates"] and normalized["fte_daily_rate"] <= 0:
            normalized["unsupported_metrics"].append("cost")

        return normalized

    @staticmethod
    def _derive_complexity_score(raw_package: Dict[str, Any]) -> float:
        complexity_label = str(raw_package.get("complexity", "")).strip().lower()
        if complexity_label in LEGACY_COMPLEXITY_MAP:
            return LEGACY_COMPLEXITY_MAP[complexity_label]
        jobs = raw_package.get("jobs", [])
        if jobs:
            values = []
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_complexity = str(job.get("complexity", "")).strip().lower()
                values.append(LEGACY_COMPLEXITY_MAP.get(job_complexity, 3.0))
            if values:
                return sum(values) / len(values)
        return 3.0

    @staticmethod
    def _derive_business_value(domain: str, job_count: int) -> float:
        """Derive business value from domain and package size.

        Uses a neutral default of 0.7.  Domain-specific overrides can be
        provided in config under ``domain_constraints.<domain>.business_value``
        or ``domain_business_values.<domain>``.  This method is a fallback
        when the package itself doesn't carry a ``business_value`` field.
        """
        # Neutral default — larger packages are slightly more valuable
        base = 0.70
        size_bonus = min(0.18, job_count / 500.0)
        return _clamp(base + size_bonus, 0.0, 1.0)

    @staticmethod
    def _derive_risk_score(
        total_effort_days: float,
        complexity_score: float,
        upstream_packages: Optional[Iterable[Any]],
    ) -> float:
        dependency_count = len(list(upstream_packages or []))
        effort_component = min(1.0, total_effort_days / 1200.0)
        complexity_component = min(1.0, complexity_score / 5.0)
        dependency_component = min(1.0, dependency_count / 6.0)
        return (effort_component + complexity_component + dependency_component) / 3.0

    @staticmethod
    def _collect_source_systems(raw_package: Dict[str, Any]) -> List[str]:
        if raw_package.get("source_systems"):
            return [str(item) for item in raw_package["source_systems"]]
        systems = set()
        for job in raw_package.get("jobs", []):
            if not isinstance(job, dict):
                continue
            for item in job.get("source_systems", []):
                systems.add(str(item))
        return sorted(systems)

    def _derive_future_core_flag(
        self, raw_package: Dict[str, Any], domain: str, raw_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        if "belongs_to_future_core" in raw_package:
            return bool(raw_package["belongs_to_future_core"])
        future_core = raw_package.get("future_core_system")
        if future_core:
            return True
        future_domains = self._future_core_domains_from_raw_config(raw_config)
        return str(domain) in future_domains

    def _future_core_domains_from_raw_config(self, raw_config: Optional[Dict[str, Any]] = None) -> Set[str]:
        """Return the set of domains designated as future-core.

        Accepts an already-loaded raw_config dict to avoid re-reading the JSON
        file.  Falls back to self.config_file if raw_config is not provided.
        """
        if raw_config is None:
            try:
                raw_config = self._load_json(self.config_file)
            except Exception:
                return set()
        if not isinstance(raw_config, dict):
            return set()
        business_rules = raw_config.get("business_rules", {})
        return set(
            raw_config.get("future_core_domains", [])
            or business_rules.get("strategic_approach_domains", [])
        )

    def _domain_business_values_from_raw_config(self, raw_config: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Read optional per-domain business value overrides from config.

        Accepts an already-loaded raw_config dict to avoid re-reading the JSON
        file.  Falls back to self.config_file if raw_config is not provided.
        """
        if raw_config is None:
            try:
                raw_config = self._load_json(self.config_file)
            except Exception:
                return {}
        if not isinstance(raw_config, dict):
            return {}
        raw_bv = raw_config.get("domain_business_values", {})
        if not isinstance(raw_bv, dict):
            return {}
        return {
            str(k).lower(): _clamp(_safe_float(v, 0.7), 0.0, 1.0)
            for k, v in raw_bv.items()
        }

    @staticmethod
    def _extract_deadline_month(raw_package: Dict[str, Any]) -> Optional[int]:
        deadline = raw_package.get("deadline_month")
        if deadline is None:
            return None
        deadline_int = _safe_int(deadline)
        return deadline_int if deadline_int > 0 else None

    @staticmethod
    def _normalize_domain_constraints(raw_constraints: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        normalized = {}
        for domain, values in raw_constraints.items():
            if not isinstance(values, dict):
                continue
            normalized[str(domain)] = {
                "earliest_start": max(0, _safe_int(values.get("earliest_start"), 0)),
                "priority_weight": _clamp(
                    _safe_float(values.get("priority_weight"), 1.0),
                    0.1,
                    3.0,
                ),
            }
        return normalized

    def _normalize_mode_parameters(self, raw_config: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        raw_modes = raw_config.get("mode_parameters") or raw_config.get("migration_modes") or {}
        normalized = {}
        for canonical_mode in MODE_ORDER:
            source_params = None
            for candidate in MODE_ALIASES[canonical_mode]:
                if candidate in raw_modes:
                    source_params = raw_modes[candidate]
                    break
            params = dict(DEFAULT_MODE_PARAMETERS[canonical_mode])
            if isinstance(source_params, dict):
                params.update(source_params)
            normalized[canonical_mode] = {
                "duration_multiplier": _safe_float(
                    params.get("duration_multiplier"),
                    DEFAULT_MODE_PARAMETERS[canonical_mode]["duration_multiplier"],
                ),
                "tech_debt_penalty": _safe_float(
                    params.get("tech_debt_penalty"),
                    DEFAULT_MODE_PARAMETERS[canonical_mode]["tech_debt_penalty"],
                ),
                "resource_efficiency": _clamp(
                    _safe_float(
                        params.get("resource_efficiency"),
                        DEFAULT_MODE_PARAMETERS[canonical_mode]["resource_efficiency"],
                    ),
                    0.1,
                    2.0,
                ),
                "base_hours": max(
                    1,
                    _safe_int(
                        params.get("base_hours"),
                        DEFAULT_MODE_PARAMETERS[canonical_mode]["base_hours"],
                    ),
                ),
                "cost_multiplier": max(
                    0.1,
                    _safe_float(
                        params.get("cost_multiplier"),
                        DEFAULT_MODE_PARAMETERS[canonical_mode]["cost_multiplier"],
                    ),
                ),
                "strategic_value": _clamp(
                    _safe_float(
                        params.get("strategic_value"),
                        DEFAULT_MODE_PARAMETERS[canonical_mode]["strategic_value"],
                    ),
                    0.0,
                    1.0,
                ),
                "future_migration_hours": max(
                    0,
                    _safe_int(
                        params.get("future_migration_hours"),
                        DEFAULT_MODE_PARAMETERS[canonical_mode]["future_migration_hours"],
                    ),
                ),
            }
        return normalized

    def _normalize_deadlines(self, raw_config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        deadlines = {}
        raw_deadlines = raw_config.get("system_deadlines", {})
        project_start_year = raw_config.get("project_start_year")
        project_start_month = _safe_int(raw_config.get("project_start_month"), 1)
        for system_name, raw_deadline in raw_deadlines.items():
            normalized = {
                "deadline_month": None,
                "affected_domains": [],
                "affected_system": system_name,
            }
            if isinstance(raw_deadline, dict):
                affected_domains = raw_deadline.get("affected_domains") or raw_deadline.get("affected_domain") or []
                if isinstance(affected_domains, str):
                    affected_domains = [affected_domains]
                normalized["affected_domains"] = [str(item) for item in affected_domains]
                deadline_month = raw_deadline.get("deadline_month")
                if deadline_month is not None:
                    normalized["deadline_month"] = max(1, _safe_int(deadline_month))
                else:
                    normalized["deadline_month"] = self._parse_deadline_month(
                        raw_deadline.get("migration_deadline") or raw_deadline.get("decommission"),
                        project_start_year,
                        project_start_month,
                    )
            elif isinstance(raw_deadline, (int, float)):
                normalized["deadline_month"] = max(1, _safe_int(raw_deadline))
            if normalized["deadline_month"]:
                deadlines[str(system_name)] = normalized
        return deadlines

    @staticmethod
    def _parse_deadline_month(
        raw_value: Any,
        project_start_year: Optional[int],
        project_start_month: int,
    ) -> Optional[int]:
        if raw_value is None:
            return None
        if isinstance(raw_value, (int, float)):
            parsed = _safe_int(raw_value)
            return parsed if parsed > 0 else None

        text = str(raw_value).strip()
        if not text:
            return None
        if text.isdigit():
            parsed = int(text)
            return parsed if parsed > 0 else None

        if not project_start_year:
            return None

        if "-Q" in text:
            year_text, quarter_text = text.split("-Q", 1)
            if year_text.isdigit() and quarter_text.isdigit():
                quarter = max(1, min(4, int(quarter_text)))
                month = (quarter - 1) * 3 + 3
                return ((int(year_text) - project_start_year) * 12) + (month - project_start_month + 1)

        # Handle reversed quarter format: "Q3 2026" or "Q3-2026"
        reversed_match = re.match(r"^Q(\d)\s*[-/]?\s*(\d{4})$", text, re.IGNORECASE)
        if reversed_match:
            quarter = max(1, min(4, int(reversed_match.group(1))))
            year = int(reversed_match.group(2))
            month = (quarter - 1) * 3 + 3
            return ((year - project_start_year) * 12) + (month - project_start_month + 1)

        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            year_text = text[0:4]
            month_text = text[5:7]
            if year_text.isdigit() and month_text.isdigit():
                return ((int(year_text) - project_start_year) * 12) + (int(month_text) - project_start_month + 1)

        return None

    @staticmethod
    def _build_job_to_package_index(packages: List[Dict[str, Any]]) -> Dict[str, str]:
        job_to_package = {}
        for package in packages:
            for job_id in package.get("job_ids", []):
                job_to_package[str(job_id)] = package["package_id"]
        return job_to_package

    def _identify_foundational_packages(self) -> Dict[str, List[str]]:
        foundational = {}
        for domain, label in self.config.get("foundational_clusters", {}).items():
            label_tokens = self._tokenize(str(label))
            matches = []
            for package in self.packages:
                if str(package["domain"]).lower() != str(domain).lower():
                    continue
                if self._matches_tokens(package["name"], label_tokens) or any(
                    self._matches_tokens(job_id, label_tokens) for job_id in package["job_ids"]
                ):
                    matches.append(package["package_id"])
            if matches:
                foundational[str(domain).lower()] = matches
        return foundational

    @staticmethod
    def _tokenize(value: str) -> List[str]:
        cleaned = value.lower().replace("-", " ").replace("_", " ").replace("/", " ")
        return [token for token in cleaned.split() if token]

    def _matches_tokens(self, text: str, expected_tokens: List[str]) -> bool:
        if not expected_tokens:
            return False
        text_tokens = self._tokenize(str(text))
        return all(token in text_tokens for token in expected_tokens)

    def _ensure_solver_available(self) -> None:
        if not CP_SAT_AVAILABLE:
            raise ImportError(
                "The ortools package is required to run the roadmap optimizer. "
                "Install it in the current environment and rerun the solve."
            )

    def _get_domain_settings(self, domain: str) -> Dict[str, float]:
        return self.config["domain_constraints"].get(
            str(domain),
            {"earliest_start": 0, "priority_weight": 1.0},
        )

    def _is_strategic_allowed(self, package: Dict[str, Any]) -> bool:
        if package.get("belongs_to_future_core") is not None:
            return bool(package["belongs_to_future_core"])

        domain = str(package["domain"])
        if domain in self.config["future_core_domains"]:
            return True

        future_core = package.get("future_core_system")
        if future_core:
            return True

        return False

    def _resolve_upstream_package_ids(self, package: Dict[str, Any]) -> List[str]:
        resolved = set()
        for upstream in package.get("upstream_packages", []):
            upstream_id = str(upstream)
            if upstream_id in self.package_by_id and upstream_id != package["package_id"]:
                resolved.add(upstream_id)
            elif upstream_id in self.job_to_package:
                candidate = self.job_to_package[upstream_id]
                if candidate != package["package_id"]:
                    resolved.add(candidate)
        return sorted(resolved)

    def _deadline_for_package(self, package: Dict[str, Any]) -> Optional[int]:
        explicit_deadline = package.get("deadline_month")
        if explicit_deadline:
            return int(explicit_deadline)

        deadlines = []
        package_domain = str(package["domain"])
        for source_system in package.get("source_systems", []):
            deadline_entry = self.config["system_deadlines"].get(str(source_system))
            if not deadline_entry:
                continue
            deadline_month = deadline_entry.get("deadline_month")
            if not deadline_month:
                continue
            affected_domains = deadline_entry.get("affected_domains") or []
            if not affected_domains or package_domain in affected_domains:
                deadlines.append(int(deadline_month))
        return min(deadlines) if deadlines else None

    def _get_mode_duration(self, package: Dict[str, Any], mode: str) -> int:
        """Calculate duration in months for a package under a given mode.

        total_effort_days already incorporates complexity (derived from job
        metadata: steps, transformations, user-code flags, etc.).  Multiplying
        by complexity_score again would double-count and produce wildly
        inflated durations.  Instead, complexity is used only as a small
        adjustment factor to capture *residual* uncertainty that the raw
        effort estimate doesn't cover (e.g. integration surprises).
        """
        params = self.config["mode_parameters"][mode]
        working_days = max(1, self.config["working_days_month"])
        team_capacity = max(1, self.config["team_capacity"])
        resource_demand = self._base_people_demand(package)
        # residual complexity adjustment: +/- 20 % around the midpoint (3.0)
        complexity_adjustment = 1.0 + (package["complexity_score"] - 3.0) * 0.1
        complexity_adjustment = max(0.7, min(1.3, complexity_adjustment))
        duration = math.ceil(
            package["total_effort_days"]
            * params["duration_multiplier"]
            * complexity_adjustment
            / (working_days * resource_demand)
        )
        return max(1, duration)

    def _base_people_demand(self, package: Dict[str, Any]) -> int:
        """Estimate how many people work on this package concurrently.

        Considers both complexity (harder packages need more senior staff)
        and package size (larger packages can absorb more parallel workers).
        The total is capped at team_capacity to keep the model feasible.
        """
        complexity = package["complexity_score"]
        effort_days = package["total_effort_days"]
        working_days = max(1, self.config["working_days_month"])

        # Size component: larger packages can absorb more parallelism
        # A 20-day package: 1 person; a 200-day package: 2; a 600+: 3
        if effort_days <= 40:
            size_demand = 1
        elif effort_days <= 200:
            size_demand = 2
        else:
            size_demand = 3

        # Complexity component: harder packages need extra people for review/QA
        if complexity >= 4.5:
            complexity_bonus = 1
        else:
            complexity_bonus = 0

        demand = size_demand + complexity_bonus
        # Never exceed team capacity
        return max(1, min(demand, self.config["team_capacity"]))

    def _get_mode_resource_demand(self, package: Dict[str, Any], mode: str) -> int:
        params = self.config["mode_parameters"][mode]
        base_demand = self._base_people_demand(package)
        adjusted = math.ceil(base_demand / params["resource_efficiency"])
        return max(1, adjusted)

    def _average_role_rate(self) -> float:
        role_rates = self.config.get("role_rates", {})
        if role_rates:
            return sum(role_rates.values()) / len(role_rates)
        return self.config.get("fte_daily_rate", 1000.0) / 8.0

    def _get_mode_cost_score(self, package: Dict[str, Any], mode: str) -> int:
        """Calculate the cost score for a package under a given mode.

        Cost scales with the package's actual effort, not a flat base_hours.
        The mode's cost_multiplier captures the overhead ratio of that
        approach (e.g. Strategic may need more architecture time).
        For build_to_legacy on future-core packages, we add the
        future_migration_hours because those packages will need a second
        migration later.
        """
        params = self.config["mode_parameters"][mode]
        average_rate = self._average_role_rate()
        # Use actual effort (in hours) scaled by the mode's cost characteristics
        effort_hours = package["total_effort_days"] * 8  # days → hours
        current_cost = effort_hours * params["cost_multiplier"] * average_rate / 1000.0
        future_cost = 0.0
        if mode == "build_to_legacy" and self._is_strategic_allowed(package):
            future_cost = params["future_migration_hours"] * average_rate / 1000.0
        return max(1, int(round(current_cost + future_cost)))

    def _get_mode_debt_score(self, package: Dict[str, Any], mode: str) -> int:
        params = self.config["mode_parameters"][mode]
        return max(0, int(round(package["complexity_score"] * 10 * params["tech_debt_penalty"])))

    def _get_mode_alignment_score(self, package: Dict[str, Any], mode: str) -> int:
        params = self.config["mode_parameters"][mode]
        return max(0, int(round(package["business_value"] * 1000 * params["strategic_value"])))

    @staticmethod
    def _weighted_term(expr: Any, upper_bound: int, weight: int, scale: int = 1000) -> Any:
        coefficient = max(1, int(round((weight * scale) / max(1, upper_bound))))
        return coefficient * expr

    def _build_model(self) -> ModelContext:
        self._ensure_solver_available()

        model = cp_model.CpModel()
        horizon = self.config["migration_horizon_months"]
        team_capacity = self.config["team_capacity"]

        start_vars: Dict[str, Any] = {}
        end_vars: Dict[str, Any] = {}
        mode_vars: Dict[str, Dict[str, Any]] = {}
        intervals: Dict[str, Dict[str, Any]] = {}
        duration_by_mode: Dict[str, Dict[str, int]] = {}
        demand_by_mode: Dict[str, Dict[str, int]] = {}
        cost_by_mode: Dict[str, Dict[str, int]] = {}
        debt_by_mode: Dict[str, Dict[str, int]] = {}
        strategic_alignment_by_mode: Dict[str, Dict[str, int]] = {}
        earliest_start_penalties: Dict[str, Any] = {}
        resolved_upstreams: Dict[str, List[str]] = {}

        all_intervals = []
        all_demands = []
        strategic_intervals = []
        strategic_demands = []

        total_cost_terms = []
        total_debt_terms = []
        strategic_alignment_terms = []
        value_delivery_terms = []
        risk_exposure_terms = []
        earliest_start_terms = []

        for package in self.packages:
            package_id = package["package_id"]
            domain_settings = self._get_domain_settings(package["domain"])
            earliest_start = int(domain_settings["earliest_start"])
            priority_weight = int(round(domain_settings["priority_weight"] * 100))
            business_value_score = max(1, int(round(package["business_value"] * 1000)))
            risk_score = max(0, int(round(package["risk_score"] * 1000)))

            start_vars[package_id] = model.NewIntVar(0, horizon, f"start_{package_id}")
            end_vars[package_id] = model.NewIntVar(0, horizon, f"end_{package_id}")
            model.Add(start_vars[package_id] >= earliest_start)

            mode_vars[package_id] = {}
            intervals[package_id] = {}
            duration_by_mode[package_id] = {}
            demand_by_mode[package_id] = {}
            cost_by_mode[package_id] = {}
            debt_by_mode[package_id] = {}
            strategic_alignment_by_mode[package_id] = {}

            active_modes = []
            for mode in MODE_ORDER:
                mode_var = model.NewBoolVar(f"{package_id}_{mode}")
                mode_vars[package_id][mode] = mode_var
                active_modes.append(mode_var)

                duration = self._get_mode_duration(package, mode)
                demand = self._get_mode_resource_demand(package, mode)
                cost_score = self._get_mode_cost_score(package, mode)
                debt_score = self._get_mode_debt_score(package, mode)
                alignment_score = self._get_mode_alignment_score(package, mode)

                duration_by_mode[package_id][mode] = duration
                demand_by_mode[package_id][mode] = demand
                cost_by_mode[package_id][mode] = cost_score
                debt_by_mode[package_id][mode] = debt_score
                strategic_alignment_by_mode[package_id][mode] = alignment_score

                intervals[package_id][mode] = model.NewOptionalIntervalVar(
                    start_vars[package_id],
                    duration,
                    end_vars[package_id],
                    mode_var,
                    f"interval_{package_id}_{mode}",
                )
                all_intervals.append(intervals[package_id][mode])
                all_demands.append(demand)
                total_cost_terms.append(cost_score * mode_var)
                total_debt_terms.append(debt_score * mode_var)
                strategic_alignment_terms.append(alignment_score * mode_var)
                if mode == "strategic":
                    strategic_intervals.append(intervals[package_id][mode])
                    strategic_demands.append(1)

            model.AddExactlyOne(active_modes)
            if not self._is_strategic_allowed(package):
                model.Add(mode_vars[package_id]["strategic"] == 0)

            # HC8: Strategic can only start after the target platform is ready
            target_ready = self.config["target_platform_ready_month"]
            if target_ready > 0:
                model.Add(
                    start_vars[package_id] >= target_ready
                ).OnlyEnforceIf(mode_vars[package_id]["strategic"])

            deadline_month = self._deadline_for_package(package)
            if deadline_month is not None:
                model.Add(end_vars[package_id] <= min(horizon, deadline_month))

            earliest_penalty = model.NewIntVar(0, earliest_start, f"early_penalty_{package_id}")
            model.Add(earliest_penalty >= earliest_start - start_vars[package_id])
            earliest_start_penalties[package_id] = earliest_penalty
            earliest_start_terms.append(priority_weight * earliest_penalty)

            value_delivery_terms.append(priority_weight * business_value_score * end_vars[package_id])
            risk_exposure_terms.append(risk_score * end_vars[package_id])

            resolved_upstreams[package_id] = self._resolve_upstream_package_ids(package)

        model.AddCumulative(all_intervals, all_demands, team_capacity)
        model.AddCumulative(
            all_intervals,
            [1 for _ in all_intervals],
            self.config["concurrent_limits"]["max_total_parallel"],
        )
        if strategic_intervals:
            model.AddCumulative(
                strategic_intervals,
                strategic_demands,
                self.config["concurrent_limits"]["max_strategic_parallel"],
            )

        for package_id, upstream_ids in resolved_upstreams.items():
            for upstream_id in upstream_ids:
                model.Add(start_vars[package_id] >= end_vars[upstream_id])

        for package in self.packages:
            package_id = package["package_id"]
            domain_key = str(package["domain"]).lower()
            foundations = self.foundational_package_ids.get(domain_key, [])
            if package_id in foundations:
                continue
            for foundation_id in foundations:
                model.Add(start_vars[package_id] >= end_vars[foundation_id])

        max_end_var = model.NewIntVar(0, horizon, "max_end")
        model.AddMaxEquality(max_end_var, list(end_vars.values()))

        bounds = self._build_metric_bounds()
        objective_terms = {
            "makespan": max_end_var,
            "total_cost": sum(total_cost_terms),
            "total_debt": sum(total_debt_terms),
            "strategic_alignment": sum(strategic_alignment_terms),
            "value_delivery": sum(value_delivery_terms),
            "risk_exposure": sum(risk_exposure_terms),
            "earliest_start_penalty": sum(earliest_start_terms),
        }
        objective_terms["cost_debt_risk"] = (
            self._weighted_term(objective_terms["total_cost"], bounds["total_cost"], 50)
            + self._weighted_term(objective_terms["total_debt"], bounds["total_debt"], 30)
            + self._weighted_term(objective_terms["risk_exposure"], bounds["risk_exposure"], 10)
            + self._weighted_term(
                objective_terms["earliest_start_penalty"],
                bounds["earliest_start_penalty"],
                10,
            )
        )
        objective_terms["fast_exit_value"] = (
            self._weighted_term(objective_terms["value_delivery"], bounds["value_delivery"], 85)
            - self._weighted_term(
                objective_terms["strategic_alignment"],
                bounds["strategic_alignment"],
                15,
            )
        )
        objective_terms["target_first_value"] = (
            self._weighted_term(objective_terms["value_delivery"], bounds["value_delivery"], 50)
            - self._weighted_term(
                objective_terms["strategic_alignment"],
                bounds["strategic_alignment"],
                50,
            )
        )
        objective_terms["balanced_score"] = (
            self._weighted_term(objective_terms["makespan"], bounds["makespan"], 40)
            + self._weighted_term(objective_terms["total_cost"], bounds["total_cost"], 15)
            + self._weighted_term(objective_terms["total_debt"], bounds["total_debt"], 10)
            + self._weighted_term(objective_terms["risk_exposure"], bounds["risk_exposure"], 15)
            + self._weighted_term(objective_terms["value_delivery"], bounds["value_delivery"], 20)
            - self._weighted_term(
                objective_terms["strategic_alignment"],
                bounds["strategic_alignment"],
                10,
            )
            + self._weighted_term(
                objective_terms["earliest_start_penalty"],
                bounds["earliest_start_penalty"],
                5,
            )
        )
        objective_terms["balanced_tiebreak"] = (
            self._weighted_term(objective_terms["total_cost"], bounds["total_cost"], 35)
            + self._weighted_term(objective_terms["total_debt"], bounds["total_debt"], 35)
            + self._weighted_term(objective_terms["risk_exposure"], bounds["risk_exposure"], 15)
            + self._weighted_term(
                objective_terms["value_delivery"],
                bounds["value_delivery"],
                15,
            )
        )

        return ModelContext(
            model=model,
            start_vars=start_vars,
            end_vars=end_vars,
            mode_vars=mode_vars,
            intervals=intervals,
            duration_by_mode=duration_by_mode,
            demand_by_mode=demand_by_mode,
            cost_by_mode=cost_by_mode,
            debt_by_mode=debt_by_mode,
            strategic_alignment_by_mode=strategic_alignment_by_mode,
            max_end_var=max_end_var,
            objective_terms=objective_terms,
            bounds=bounds,
            earliest_start_penalties=earliest_start_penalties,
            resolved_upstreams=resolved_upstreams,
        )

    def _build_metric_bounds(self) -> Dict[str, int]:
        horizon = self.config["migration_horizon_months"]
        total_cost = 0
        total_debt = 0
        value_delivery = 0
        risk_exposure = 0
        strategic_alignment = 0
        earliest_start_penalty = 0

        for package in self.packages:
            domain_settings = self._get_domain_settings(package["domain"])
            priority_weight = int(round(domain_settings["priority_weight"] * 100))
            business_value_score = max(1, int(round(package["business_value"] * 1000)))
            risk_score = max(0, int(round(package["risk_score"] * 1000)))

            mode_costs = [self._get_mode_cost_score(package, mode) for mode in MODE_ORDER]
            mode_debts = [self._get_mode_debt_score(package, mode) for mode in MODE_ORDER]
            mode_alignments = [
                self._get_mode_alignment_score(package, mode) for mode in MODE_ORDER
            ]

            total_cost += max(mode_costs)
            total_debt += max(mode_debts)
            strategic_alignment += max(mode_alignments)
            value_delivery += priority_weight * business_value_score * horizon
            risk_exposure += risk_score * horizon
            earliest_start_penalty += int(domain_settings["earliest_start"]) * priority_weight

        return {
            "makespan": max(1, horizon),
            "total_cost": max(1, total_cost),
            "total_debt": max(1, total_debt),
            "value_delivery": max(1, value_delivery),
            "risk_exposure": max(1, risk_exposure),
            "strategic_alignment": max(1, strategic_alignment),
            "earliest_start_penalty": max(1, earliest_start_penalty),
        }

    def _scenario_stage_plan(self, scenario_name: str) -> List[Tuple[str, str, str]]:
        if scenario_name == "Fast Exit":
            return [
                ("Minimize Duration", "makespan", "min"),
                ("Minimize Cost+Debt", "cost_debt_risk", "min"),
                ("Improve Value Delivery", "fast_exit_value", "min"),
            ]
        if scenario_name == "Balanced":
            return [
                ("Minimize Balanced Score", "balanced_score", "min"),
                ("Minimize Duration", "makespan", "min"),
                ("Minimize Tie-Break Cost", "balanced_tiebreak", "min"),
            ]
        if scenario_name == "Target-First":
            return [
                ("Maximize Strategic Alignment", "strategic_alignment", "max"),
                ("Minimize Value Delivery Time", "value_delivery", "min"),
                ("Minimize Duration", "makespan", "min"),
                ("Minimize Cost+Debt", "cost_debt_risk", "min"),
            ]
        raise ValueError(f"Unsupported scenario name: {scenario_name}")

    def _apply_objective_locks(
        self,
        context: ModelContext,
        locks: List[Dict[str, Any]],
    ) -> None:
        for lock in locks:
            expr = context.objective_terms[lock["metric_key"]]
            if lock["sense"] == "min":
                context.model.Add(expr <= lock["value"])
            else:
                context.model.Add(expr >= lock["value"])

    def _apply_solution_hints(
        self,
        context: ModelContext,
        hints: Optional[Dict[str, Dict[str, Any]]],
    ) -> None:
        if not hints:
            return
        for package_id, value in hints.get("start_vars", {}).items():
            context.model.AddHint(context.start_vars[package_id], value)
        for package_id, value in hints.get("end_vars", {}).items():
            context.model.AddHint(context.end_vars[package_id], value)
        for package_id, mode_values in hints.get("mode_vars", {}).items():
            for mode, value in mode_values.items():
                context.model.AddHint(context.mode_vars[package_id][mode], value)

    @staticmethod
    def _collect_solution_hints(context: ModelContext, solver: Any) -> Dict[str, Dict[str, Any]]:
        return {
            "start_vars": {
                package_id: solver.Value(variable)
                for package_id, variable in context.start_vars.items()
            },
            "end_vars": {
                package_id: solver.Value(variable)
                for package_id, variable in context.end_vars.items()
            },
            "mode_vars": {
                package_id: {
                    mode: solver.Value(variable)
                    for mode, variable in modes.items()
                }
                for package_id, modes in context.mode_vars.items()
            },
        }

    def _create_solver(self, max_time_seconds: float) -> Any:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(1.0, max_time_seconds)
        solver.parameters.num_search_workers = max(
            1, self.config["solver"]["num_search_workers"]
        )
        solver.parameters.random_seed = self.config["solver"]["random_seed"]
        return solver

    def solve_scenario(self, scenario_name: str) -> OptimizationResult:
        """Solve one scenario using staged exact optimization."""
        self._ensure_solver_available()
        print(f"Solving scenario: {scenario_name}")

        stage_plan = self._scenario_stage_plan(scenario_name)
        locks: List[Dict[str, Any]] = []
        stage_outcomes: List[StageOutcome] = []
        hints: Optional[Dict[str, Dict[str, Any]]] = None
        final_context: Optional[ModelContext] = None
        final_solver = None
        final_status = None
        scenario_start = time.perf_counter()
        scenario_budget = self.config["solver"]["max_time_in_seconds"]

        for stage_index, (stage_name, metric_key, sense) in enumerate(stage_plan):
            elapsed = time.perf_counter() - scenario_start
            remaining = max(1.0, scenario_budget - elapsed)
            stages_left = len(stage_plan) - stage_index
            stage_budget = max(5.0, remaining / stages_left)

            context = self._build_model()
            self._apply_objective_locks(context, locks)
            self._apply_solution_hints(context, hints)

            objective_expr = context.objective_terms[metric_key]
            if sense == "min":
                context.model.Minimize(objective_expr)
            else:
                context.model.Maximize(objective_expr)

            solver = self._create_solver(stage_budget)
            stage_start = time.perf_counter()
            status = solver.Solve(context.model)
            stage_elapsed = time.perf_counter() - stage_start

            status_name = _status_name(status)
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                raise RuntimeError(
                    f"{scenario_name} failed during '{stage_name}' with status {status_name}."
                )

            metric_value = int(solver.Value(objective_expr))
            locks.append(
                {
                    "stage_name": stage_name,
                    "metric_key": metric_key,
                    "sense": sense,
                    "value": metric_value,
                }
            )
            hints = self._collect_solution_hints(context, solver)
            stage_outcomes.append(
                StageOutcome(
                    stage_name=stage_name,
                    metric_key=metric_key,
                    sense=sense,
                    status=status_name,
                    target_value=metric_value,
                    solve_time_seconds=stage_elapsed,
                    objective_value=solver.ObjectiveValue(),
                    best_bound=solver.BestObjectiveBound(),
                )
            )

            final_context = context
            final_solver = solver
            final_status = status

        if not final_context or final_solver is None or final_status is None:
            raise RuntimeError(f"{scenario_name} did not produce a solution.")

        return self._extract_solution(
            scenario_name=scenario_name,
            context=final_context,
            solver=final_solver,
            final_status=final_status,
            stage_outcomes=stage_outcomes,
            total_solve_time=time.perf_counter() - scenario_start,
        )

    def _extract_solution(
        self,
        scenario_name: str,
        context: ModelContext,
        solver: Any,
        final_status: int,
        stage_outcomes: List[StageOutcome],
        total_solve_time: float,
    ) -> OptimizationResult:
        schedule: List[Dict[str, Any]] = []
        packages_by_mode = {mode: 0 for mode in MODE_ORDER}
        total_effort = 0.0
        strategic_effort = 0.0
        technical_debt_score = 0
        total_cost_score = 0
        risk_exposure_score = 0

        for package in self.packages:
            package_id = package["package_id"]
            start_month = solver.Value(context.start_vars[package_id])
            end_month = solver.Value(context.end_vars[package_id])
            selected_mode = None
            for mode in MODE_ORDER:
                if solver.Value(context.mode_vars[package_id][mode]) == 1:
                    selected_mode = mode
                    packages_by_mode[mode] += 1
                    break
            if selected_mode is None:
                raise RuntimeError(f"No mode selected for package '{package_id}'.")

            total_effort += package["total_effort_days"]
            if selected_mode == "strategic":
                strategic_effort += package["total_effort_days"]

            technical_debt_score += context.debt_by_mode[package_id][selected_mode]
            total_cost_score += context.cost_by_mode[package_id][selected_mode]
            risk_exposure_score += int(round(package["risk_score"] * 1000 * end_month))

            schedule.append(
                {
                    "package_id": package_id,
                    "package_name": package["name"],
                    "domain": package["domain"],
                    "start_month": start_month,
                    "end_month": end_month,
                    "duration_months": end_month - start_month,
                    "selected_mode": selected_mode,
                    "effort_days": package["total_effort_days"],
                    "business_value": package["business_value"],
                    "assigned_team": package.get("assigned_team"),
                    "dependencies_met": True,
                    "risk_factors": self._risk_factors(package),
                }
            )

        schedule.sort(key=lambda item: (item["start_month"], item["package_id"]))
        total_duration = max((item["end_month"] for item in schedule), default=0)
        resource_utilization, monthly_usage = self._compute_resource_utilization(
            schedule, context
        )
        strategic_coverage = (
            strategic_effort / total_effort if total_effort > 0 else 0.0
        )
        constraint_violations = self._verify_solution(schedule, context, monthly_usage)

        proof_status = (
            "OPTIMAL"
            if all(outcome.status == "OPTIMAL" for outcome in stage_outcomes)
            else "BEST_FOUND"
        )
        final_gap = self._compute_optimality_gap(solver)

        return OptimizationResult(
            scenario_name=scenario_name,
            total_duration_months=total_duration,
            packages_by_mode=packages_by_mode,
            resource_utilization=resource_utilization,
            technical_debt_score=technical_debt_score,
            strategic_coverage=strategic_coverage,
            schedule=schedule,
            objective_value=float(stage_outcomes[-1].target_value),
            objective_breakdown={
                "stage_outcomes": [asdict(outcome) for outcome in stage_outcomes],
                "metrics": {
                    "makespan": solver.Value(context.objective_terms["makespan"]),
                    "total_cost": solver.Value(context.objective_terms["total_cost"]),
                    "total_debt": solver.Value(context.objective_terms["total_debt"]),
                    "strategic_alignment": solver.Value(
                        context.objective_terms["strategic_alignment"]
                    ),
                    "value_delivery": solver.Value(context.objective_terms["value_delivery"]),
                    "risk_exposure": solver.Value(context.objective_terms["risk_exposure"]),
                    "earliest_start_penalty": solver.Value(
                        context.objective_terms["earliest_start_penalty"]
                    ),
                },
                "unsupported_metrics": [],  # quality is validated at execution time, not scheduling
            },
            solver_statistics={
                "status": _status_name(final_status),
                "solve_time_seconds": round(total_solve_time, 4),
                "optimality_gap": final_gap,
                "conflicts": solver.NumConflicts(),
                "branches": solver.NumBranches(),
                "wall_time_seconds": round(solver.WallTime(), 4),
                "variables": len(context.model.Proto().variables),
                "constraints": len(context.model.Proto().constraints),
                "stage_statistics": [asdict(outcome) for outcome in stage_outcomes],
            },
            proof_status=proof_status,
            constraint_violations=constraint_violations,
            total_cost_score=float(total_cost_score),
            risk_exposure_score=float(risk_exposure_score),
        )

    @staticmethod
    def _compute_optimality_gap(solver: Any) -> Optional[float]:
        try:
            objective = solver.ObjectiveValue()
            bound = solver.BestObjectiveBound()
        except Exception:
            return None
        denominator = max(1.0, abs(objective))
        return round(abs(objective - bound) / denominator, 6)

    @staticmethod
    def _risk_factors(package: Dict[str, Any]) -> List[str]:
        factors = []
        if package["risk_score"] >= 0.7:
            factors.append("high_risk")
        if package["complexity_score"] > 4.0:
            factors.append("high_complexity")
        if package["upstream_packages"]:
            factors.append("dependency_heavy")
        return factors

    def _compute_resource_utilization(
        self,
        schedule: List[Dict[str, Any]],
        context: ModelContext,
    ) -> Tuple[float, Dict[int, Dict[str, int]]]:
        if not schedule:
            return 0.0, {}

        monthly_usage: Dict[int, Dict[str, int]] = {}
        team_capacity = self.config["team_capacity"]
        total_duration = max(item["end_month"] for item in schedule)

        for month in range(total_duration):
            people_used = 0
            active_packages = 0
            active_strategic = 0
            for item in schedule:
                if item["start_month"] <= month < item["end_month"]:
                    package_id = item["package_id"]
                    selected_mode = item["selected_mode"]
                    people_used += context.demand_by_mode[package_id][selected_mode]
                    active_packages += 1
                    if selected_mode == "strategic":
                        active_strategic += 1
            monthly_usage[month] = {
                "people_used": people_used,
                "active_packages": active_packages,
                "active_strategic": active_strategic,
            }

        average_utilization = sum(
            usage["people_used"] / team_capacity for usage in monthly_usage.values()
        ) / max(1, len(monthly_usage))
        return round(average_utilization, 4), monthly_usage

    def _verify_solution(
        self,
        schedule: List[Dict[str, Any]],
        context: ModelContext,
        monthly_usage: Dict[int, Dict[str, int]],
    ) -> List[Dict[str, str]]:
        violations = []
        lookup = {item["package_id"]: item for item in schedule}

        for package_id, upstream_ids in context.resolved_upstreams.items():
            for upstream_id in upstream_ids:
                if lookup[package_id]["start_month"] < lookup[upstream_id]["end_month"]:
                    violations.append(
                        {
                            "constraint_type": "precedence",
                            "violation_description": (
                                f"{package_id} starts before upstream {upstream_id} finishes."
                            ),
                            "severity": "error",
                        }
                    )

        for month, usage in monthly_usage.items():
            if usage["people_used"] > self.config["team_capacity"]:
                violations.append(
                    {
                        "constraint_type": "capacity",
                        "violation_description": (
                            f"Month {month} exceeds team capacity ({usage['people_used']} > "
                            f"{self.config['team_capacity']})."
                        ),
                        "severity": "error",
                    }
                )
            if usage["active_packages"] > self.config["concurrent_limits"]["max_total_parallel"]:
                violations.append(
                    {
                        "constraint_type": "parallelism",
                        "violation_description": (
                            f"Month {month} exceeds max total in-flight packages."
                        ),
                        "severity": "error",
                    }
                )
            if usage["active_strategic"] > self.config["concurrent_limits"]["max_strategic_parallel"]:
                violations.append(
                    {
                        "constraint_type": "strategic_parallelism",
                        "violation_description": (
                            f"Month {month} exceeds max strategic packages in flight."
                        ),
                        "severity": "error",
                    }
                )

        return violations

    def run_all_scenarios(self) -> List[OptimizationResult]:
        """Run all three canonical scenarios."""
        results = []
        for scenario_name in SCENARIO_FILES:
            results.append(self.solve_scenario(scenario_name))
        return results

    @staticmethod
    def _result_to_dict(result: OptimizationResult) -> Dict[str, Any]:
        return asdict(result)

    def recommend_scenario(self, results: List[OptimizationResult]) -> Dict[str, Any]:
        """Rank scenarios and recommend the best one.

        Uses configurable recommendation_weights from the config (falls back
        to DEFAULT_RECOMMENDATION_WEIGHTS).  Lower score = better scenario.
        """
        if not results:
            raise ValueError("Cannot recommend a scenario without results.")

        weights = self.config.get("recommendation_weights", DEFAULT_RECOMMENDATION_WEIGHTS)
        w_duration = _safe_float(weights.get("duration"), 0.35)
        w_debt = _safe_float(weights.get("tech_debt"), 0.25)
        w_strategic = _safe_float(weights.get("strategic_coverage"), 0.25)
        w_util = _safe_float(weights.get("utilization_deviation"), 0.10)
        w_proof = _safe_float(weights.get("proof_penalty"), 0.15)

        durations = [result.total_duration_months for result in results]
        debts = [result.technical_debt_score for result in results]
        strategics = [result.strategic_coverage for result in results]

        def normalize(value: float, values: List[float], invert: bool = False) -> float:
            minimum = min(values)
            maximum = max(values)
            if math.isclose(minimum, maximum):
                score = 0.0
            else:
                score = (value - minimum) / (maximum - minimum)
            return 1.0 - score if invert else score

        ranked = []
        for result in results:
            utilization_penalty = abs(result.resource_utilization - 0.8)
            proof_penalty = 0.0 if result.proof_status == "OPTIMAL" else w_proof
            score = (
                w_duration * normalize(result.total_duration_months, durations)
                + w_debt * normalize(result.technical_debt_score, debts)
                + w_strategic * normalize(result.strategic_coverage, strategics, invert=True)
                + w_util * utilization_penalty
                + proof_penalty
            )
            ranked.append(
                {
                    "scenario_name": result.scenario_name,
                    "recommendation_score": round(score, 6),
                    "proof_status": result.proof_status,
                    "duration_months": result.total_duration_months,
                    "strategic_coverage": result.strategic_coverage,
                    "technical_debt_score": result.technical_debt_score,
                    "resource_utilization": result.resource_utilization,
                }
            )

        ranked.sort(key=lambda item: item["recommendation_score"])
        recommendation = ranked[0]
        recommendation["reason"] = (
            "Lowest cross-scenario score after balancing duration, technical debt, "
            "strategic coverage, utilization, and proof status."
        )
        recommendation["all_scenarios"] = ranked
        return recommendation

    def save_results(self, results: List[OptimizationResult], output_dir: str) -> None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_results_payload = {}
        for result in results:
            scenario_key = SCENARIO_FILES[result.scenario_name]
            result_dict = self._result_to_dict(result)
            all_results_payload[scenario_key] = result_dict
            with open(
                output_path / f"{scenario_key}_result.json",
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(result_dict, handle, indent=2)

        recommendation = self.recommend_scenario(results)
        with open(
            output_path / "recommended_scenario.json",
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(recommendation, handle, indent=2)

        with open(
            output_path / "all_scenarios_result.json",
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(all_results_payload, handle, indent=2)

    def generate_comparison_report(
        self,
        results: List[OptimizationResult],
        output_dir: str,
    ) -> None:
        """Generate CSV and optional PNG comparisons for scenario results."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        comparison_rows = []
        for result in results:
            comparison_rows.append(
                {
                    "Scenario": result.scenario_name,
                    "Proof Status": result.proof_status,
                    "Duration (months)": result.total_duration_months,
                    "Strategic Coverage (%)": round(result.strategic_coverage * 100, 2),
                    "Tech Debt Score": round(result.technical_debt_score, 2),
                    "Resource Utilization (%)": round(result.resource_utilization * 100, 2),
                    "Cost Score": round(result.total_cost_score, 2),
                    "Build-to-Legacy": result.packages_by_mode["build_to_legacy"],
                    "Bridge-to-Model": result.packages_by_mode["bridge_to_model"],
                    "Strategic": result.packages_by_mode["strategic"],
                }
            )

        with open(
            output_path / "scenario_comparison.csv",
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0].keys()))
            writer.writeheader()
            writer.writerows(comparison_rows)

        for result in results:
            schedule_path = output_path / (
                f"{SCENARIO_FILES[result.scenario_name]}_schedule.csv"
            )
            with open(schedule_path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(result.schedule[0].keys()))
                writer.writeheader()
                writer.writerows(result.schedule)

        self._create_visualizations(results, output_path)

    def _create_visualizations(self, results: List[OptimizationResult], output_path: Path) -> None:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            import warnings
            warnings.warn(
                "matplotlib is not installed — skipping Gantt and comparison chart generation. "
                "Install it with: pip install matplotlib",
                stacklevel=2,
            )
            return

        self._create_gantt_charts(results, output_path, plt)
        self._create_comparison_charts(results, output_path, plt)

    def _create_gantt_charts(self, results: List[OptimizationResult], output_path: Path, plt: Any) -> None:
        mode_colors = {
            "build_to_legacy": "#d97b67",
            "bridge_to_model": "#6a7db3",
            "strategic": "#4d9a6b",
        }
        for result in results:
            fig, ax = plt.subplots(figsize=(15, 10))
            schedule = list(result.schedule)
            y_positions = range(len(schedule))

            for index, task in enumerate(schedule):
                start = task["start_month"]
                duration = task["duration_months"]
                mode = task["selected_mode"]
                ax.barh(
                    index,
                    duration,
                    left=start,
                    height=0.8,
                    color=mode_colors[mode],
                    alpha=0.8,
                )
                ax.text(
                    start + max(1, duration / 2),
                    index,
                    task["package_name"][:24],
                    ha="center",
                    va="center",
                    fontsize=8,
                )

            ax.set_yticks(list(y_positions))
            ax.set_yticklabels([task["package_name"][:28] for task in schedule])
            ax.set_xlabel("Month")
            ax.set_title(f"Migration Schedule - {result.scenario_name}")
            ax.grid(True, alpha=0.25)
            plt.tight_layout()
            plt.savefig(
                output_path / f"{SCENARIO_FILES[result.scenario_name]}_gantt.png",
                dpi=300,
            )
            plt.close(fig)

    def _create_comparison_charts(self, results: List[OptimizationResult], output_path: Path, plt: Any) -> None:
        scenarios = [result.scenario_name for result in results]
        durations = [result.total_duration_months for result in results]
        strategics = [result.strategic_coverage * 100 for result in results]
        debt_scores = [result.technical_debt_score for result in results]
        build_counts = [result.packages_by_mode["build_to_legacy"] for result in results]
        bridge_counts = [result.packages_by_mode["bridge_to_model"] for result in results]
        strategic_counts = [result.packages_by_mode["strategic"] for result in results]

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        axes[0, 0].bar(scenarios, durations, color=["#d97b67", "#d4a72c", "#4d9a6b"])
        axes[0, 0].set_title("Total Duration (Months)")

        axes[0, 1].bar(scenarios, strategics, color=["#d97b67", "#d4a72c", "#4d9a6b"])
        axes[0, 1].set_title("Strategic Coverage (%)")

        axes[1, 0].bar(scenarios, debt_scores, color=["#d97b67", "#d4a72c", "#4d9a6b"])
        axes[1, 0].set_title("Technical Debt Score")

        axes[1, 1].bar(scenarios, build_counts, label="Build-to-Legacy", color="#d97b67")
        axes[1, 1].bar(
            scenarios,
            bridge_counts,
            bottom=build_counts,
            label="Bridge-to-Model",
            color="#6a7db3",
        )
        axes[1, 1].bar(
            scenarios,
            strategic_counts,
            bottom=[build + bridge for build, bridge in zip(build_counts, bridge_counts)],
            label="Strategic",
            color="#4d9a6b",
        )
        axes[1, 1].set_title("Mode Distribution")
        axes[1, 1].legend()

        plt.tight_layout()
        plt.savefig(output_path / "scenario_comparison.png", dpi=300)
        plt.close(fig)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the roadmap optimizer: aggregate packages, solve "
        "multiple scenarios, and generate comparison reports.",
    )
    parser.add_argument(
        "packages_file",
        help="Path to JSON file containing migration packages",
    )
    parser.add_argument(
        "config_file",
        help="Path to JSON configuration file",
    )
    parser.add_argument(
        "output_dir",
        help="Directory to write result JSON, CSV, and PNG files",
    )
    parser.add_argument(
        "--scenario",
        choices=["fast_exit", "balanced", "target_first"],
        default=None,
        help="Run only a single scenario (default: run all three)",
    )
    args = parser.parse_args()

    solver = MRCSPSolver(args.packages_file, args.config_file)

    if args.scenario:
        # Map CLI name → display name
        scenario_display = {
            "fast_exit": "Fast Exit",
            "balanced": "Balanced",
            "target_first": "Target-First",
        }
        print(f"Running {scenario_display[args.scenario]} scenario...")
        results = [solver.solve_scenario(scenario_display[args.scenario])]
    else:
        print("Running all optimization scenarios...")
        results = solver.run_all_scenarios()

    print("Saving scenario results...")
    solver.save_results(results, args.output_dir)

    print("Generating comparison assets...")
    solver.generate_comparison_report(results, args.output_dir)

    print(f"Optimization complete. Results saved to {args.output_dir}")


if __name__ == "__main__":
    main()
