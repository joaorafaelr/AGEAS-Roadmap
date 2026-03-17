#!/usr/bin/env python3
"""
Canonical SAS metadata normalization for the roadmap optimizer.
"""

from __future__ import annotations

import argparse
import json
import re
from bisect import bisect_right
from pathlib import Path
from statistics import fmean
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_DOMAIN_TAXONOMY = {
    "default_domains": ["Claims", "Entities", "Policies"],
    "aliases": {
        "Claims": ["claim", "claims", "sinistro", "duck creek", "dc claims", "dc_"],
        "Entities": ["entity", "entities", "pessoas", "edm", "personas"],
        "Policies": ["policy", "policies", "apolice", "poliza", "polaris", "aia"],
    },
}

DEFAULT_SOURCE_SYSTEM_RULES = [
    {
        "name": "DC Policy",
        "patterns": ["duck creek", "duckcreek", "dwjb_dia_dc_", "cod_sourcesystem = 'DUCKCREEK'"],
        "default_domain": "Policies",
    },
    {
        "name": "DC Claims",
        "patterns": ["claims", "claim", "sinistro", "clm_"],
        "default_domain": "Claims",
        "future_core_system": "DC Claims",
    },
    {
        "name": "EDM",
        "patterns": ["entity", "entities", "personas", "pessoas", "edm"],
        "default_domain": "Entities",
        "future_core_system": "EDM",
    },
    {
        "name": "Polaris",
        "patterns": ["polaris", "policy core", "apolice", "poliza"],
        "default_domain": "Policies",
        "future_core_system": "Polaris",
    },
    {"name": "CCS", "patterns": ["ccs"], "default_domain": "Claims"},
    {"name": "Tecnisys", "patterns": ["tecnisys", "tec_"], "default_domain": "Policies"},
    {"name": "Cogen", "patterns": ["cogen", "cgn_"], "default_domain": "Policies"},
    {"name": "AIA", "patterns": ["aia"], "default_domain": "Policies"},
    {"name": "NICF", "patterns": ["nicf"], "default_domain": "Policies"},
]

DEFAULT_CONFIDENCE_THRESHOLDS = {
    "low": 0.45,
    "medium": 0.7,
    "high": 0.85,
    "strategic_minimum": 0.6,
}

DEFAULT_MODE_ELIGIBILITY_RULES = {
    "future_core_by_domain": {
        "Claims": "DC Claims",
        "Entities": "EDM",
        "Policies": "Polaris",
    },
    "analytical_model_domain_map": {
        "UNO": ["Claims"],
        "MAE": ["Entities"],
        "MAOC": ["Policies"],
    },
    "strategic_min_similarity": 70.0,
    "low_confidence_penalty_multiplier": 1.3,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _percentile_rank(value: float, distribution: List[float]) -> float:
    if not distribution:
        return 0.0
    sorted_values = sorted(distribution)
    return bisect_right(sorted_values, value) / len(sorted_values)


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


class DWReportIndex:
    """Index DW report facts by job id for business enrichment."""

    def __init__(self) -> None:
        self.job_index: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def from_directory(cls, report_dir: Optional[Path]) -> "DWReportIndex":
        index = cls()
        if not report_dir or not report_dir.exists():
            return index

        for report_path in sorted(report_dir.glob("*_DW_Report.txt")):
            index._parse_report(report_path)
        return index

    def _parse_report(self, report_path: Path) -> None:
        domain = report_path.stem.replace("_DW_Report", "")
        current_insurance_type: Optional[str] = None
        current_subcluster: Optional[str] = None
        current_job: Optional[Dict[str, Any]] = None

        lines = report_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for raw_line in lines:
            line = raw_line.rstrip()
            insurance_match = re.search(r"INSURANCE TYPE:\s*([A-Z-]+(?:\s+[A-Z-]+)*)", line)
            if insurance_match:
                current_insurance_type = insurance_match.group(1).title()
                continue

            subcluster_match = re.search(r"Sub-cluster:\s+(.+?)\s+\((\d+)\s+jobs\)", line)
            if subcluster_match:
                current_subcluster = subcluster_match.group(1).strip()
                if current_job and current_job.get("job_id"):
                    self.job_index[current_job["job_id"]] = current_job
                current_job = None
                continue

            job_header = re.match(r"\s*\[(\d+)\]\s+(.+)$", line)
            if job_header:
                if current_job and current_job.get("job_id"):
                    self.job_index[current_job["job_id"]] = current_job
                current_job = {
                    "domain": domain,
                    "subcluster": current_subcluster,
                    "insurance_type": current_insurance_type,
                    "job_name": job_header.group(2).strip(),
                }
                continue

            if current_job is None:
                continue

            if "Job ID:" in line:
                current_job["job_id"] = line.split("Job ID:", 1)[1].strip()
            elif "Folder:" in line:
                current_job["folder_path"] = line.split("Folder:", 1)[1].strip()
            elif "Has user code:" in line:
                current_job["has_user_code"] = "yes" in line.lower()
            elif "Upstream jobs:" in line:
                current_job["report_upstream_jobs"] = [
                    item.strip()
                    for item in line.split("Upstream jobs:", 1)[1].split(",")
                    if item.strip()
                ]
            elif "Downstream jobs:" in line:
                current_job["report_downstream_jobs"] = [
                    item.strip()
                    for item in line.split("Downstream jobs:", 1)[1].split(",")
                    if item.strip()
                ]

        if current_job and current_job.get("job_id"):
            self.job_index[current_job["job_id"]] = current_job


class SASMetadataNormalizer:
    """Normalize SAS job metadata into the canonical roadmap schema."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        business_mapping: Optional[Dict[str, Any]] = None,
        roadmap_overrides: Optional[Dict[str, Any]] = None,
        report_dir: Optional[Path] = None,
        similarity_scores_path: Optional[Path] = None,
    ) -> None:
        self.config = config or {}
        self.business_mapping = business_mapping or {}
        self.roadmap_overrides = roadmap_overrides or {}
        self.domain_taxonomy = self.config.get("domain_taxonomy", DEFAULT_DOMAIN_TAXONOMY)
        self.source_system_rules = self.config.get("source_system_rules", DEFAULT_SOURCE_SYSTEM_RULES)
        self.confidence_thresholds = self.config.get("confidence_thresholds", DEFAULT_CONFIDENCE_THRESHOLDS)
        self.mode_eligibility_rules = self.config.get("mode_eligibility_rules", DEFAULT_MODE_ELIGIBILITY_RULES)
        self.dw_index = DWReportIndex.from_directory(report_dir)
        self.similarity_scores = self._load_similarity_scores(similarity_scores_path)
        self._job_feature_distributions: Dict[str, List[float]] = {}

    def normalize_jobs_from_source(self, source_path: Path) -> List[Dict[str, Any]]:
        raw_jobs = self._load_source_records(source_path)
        return self.normalize_jobs(raw_jobs)

    def normalize_jobs(self, raw_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        stage_one = [self._extract_base_job(raw_job) for raw_job in raw_jobs]
        self._prepare_feature_distributions(stage_one)
        return [self._enrich_job(job) for job in stage_one]

    def summarize_jobs(self, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not jobs:
            return {
                "job_count": 0,
                "unknown_domain_count": 0,
                "low_confidence_count": 0,
                "future_core_candidates": 0,
                "source_system_coverage": 0.0,
                "assumption_count": 0,
            }

        low_threshold = _safe_float(self.confidence_thresholds.get("low"), 0.45)
        source_coverage = sum(1 for job in jobs if job.get("source_systems")) / len(jobs)
        assumption_count = sum(len(job.get("assumptions", [])) for job in jobs)
        return {
            "job_count": len(jobs),
            "unknown_domain_count": sum(1 for job in jobs if job.get("domain") == "Unknown"),
            "low_confidence_count": sum(
                1
                for job in jobs
                if _safe_float(job.get("confidence", {}).get("overall")) < low_threshold
            ),
            "future_core_candidates": sum(1 for job in jobs if job.get("future_core_candidate")),
            "source_system_coverage": round(source_coverage, 4),
            "assumption_count": assumption_count,
        }

    def _load_source_records(self, source_path: Path) -> List[Dict[str, Any]]:
        if source_path.is_dir():
            return [_load_json(json_path) for json_path in sorted(source_path.glob("*.json"))]
        if source_path.suffix.lower() == ".jsonl":
            return _load_jsonl(source_path)

        payload = _load_json(source_path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
        raise ValueError(f"Unsupported job source format at '{source_path}'.")

    def _prepare_feature_distributions(self, jobs: List[Dict[str, Any]]) -> None:
        numeric_fields = [
            "steps_count",
            "transformations_count",
            "source_tables_count",
            "target_tables_count",
            "temp_tables_count",
            "fan_in",
            "fan_out",
        ]
        distributions: Dict[str, List[float]] = {field: [] for field in numeric_fields}
        for job in jobs:
            for field in numeric_fields:
                distributions[field].append(_safe_float(job.get(field), 0.0))
        self._job_feature_distributions = distributions

    def _extract_base_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        if "meta" in raw_job and "overview" in raw_job:
            return self._extract_local_sas_job(raw_job)
        if "job_steps" in raw_job or "job_dependencies" in raw_job:
            return self._extract_structured_job(raw_job)
        if "step_names" in raw_job or "input_table_names" in raw_job:
            return self._extract_profile_job(raw_job)
        return self._extract_generic_job(raw_job)

    def _extract_local_sas_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        meta = raw_job.get("meta", {})
        overview = raw_job.get("overview", {})
        flow_steps = raw_job.get("flow", {}).get("steps", [])
        lineage = raw_job.get("lineage", {})

        source_tables = []
        target_tables = []
        temp_tables = []
        step_kinds = []
        simplified_steps = []
        for item in flow_steps:
            step = item.get("step", {})
            step_kinds.append(step.get("step_kind", "step"))
            reads = item.get("reads", [])
            writes = item.get("writes", [])
            source_tables.extend(entry.get("table_name") for entry in reads if entry.get("table_name"))
            target_tables.extend(entry.get("table_name") for entry in writes if entry.get("table_name"))
            temp_tables.extend(
                entry.get("table_name")
                for entry in writes
                if entry.get("table_name", "").startswith("W")
            )
            simplified_steps.append(
                {
                    "step_id": step.get("step_id"),
                    "step_name": step.get("step_name"),
                    "step_kind": step.get("step_kind", "step"),
                }
            )

        upstream = [
            item.get("job_id")
            for item in lineage.get("upstream_jobs", [])
            if isinstance(item, dict) and item.get("job_id")
        ]
        downstream = [
            item.get("job_id")
            for item in lineage.get("downstream_jobs", [])
            if isinstance(item, dict) and item.get("job_id")
        ]
        via_tables = _dedupe(
            table
            for dep_group in (lineage.get("upstream_jobs", []) + lineage.get("downstream_jobs", []))
            if isinstance(dep_group, dict)
            for table in dep_group.get("via_tables", [])
        )

        return {
            "job_id": str(meta.get("job_id") or raw_job.get("job_id")),
            "job_name": str(meta.get("job_name") or raw_job.get("job_name") or meta.get("job_id")),
            "folder_path": str(meta.get("folder_path") or raw_job.get("folder_path") or ""),
            "job_kind": str(meta.get("job_kind") or raw_job.get("job_kind") or "etl_job"),
            "steps": simplified_steps,
            "steps_count": _safe_int(overview.get("steps_count"), len(flow_steps)),
            "transformations_count": _safe_int(overview.get("transformations_count")),
            "has_user_code": bool(overview.get("has_user_code")),
            "source_tables": _dedupe(source_tables),
            "target_tables": _dedupe(target_tables),
            "temp_tables": _dedupe(temp_tables),
            "source_tables_count": _safe_int(overview.get("source_tables_count"), len(source_tables)),
            "target_tables_count": _safe_int(overview.get("target_tables_count"), len(target_tables)),
            "temp_tables_count": len(_dedupe(temp_tables)),
            "source_columns_count": _safe_int(overview.get("source_used_columns_count")),
            "target_columns_count": _safe_int(overview.get("target_written_columns_count")),
            "step_kinds": _dedupe(step_kinds),
            "upstream_dependencies": _dedupe(upstream),
            "downstream_dependencies": _dedupe(downstream),
            "via_tables": via_tables,
            "raw_domain": raw_job.get("domain"),
            "fan_in": len(_dedupe(upstream)),
            "fan_out": len(_dedupe(downstream)),
        }

    def _extract_structured_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        steps = raw_job.get("job_steps", [])
        source_tables = _dedupe(
            table.get("table_name")
            for step in steps
            for table in step.get("source_tables", [])
            if isinstance(table, dict) and table.get("table_name")
        )
        target_tables = _dedupe(
            table.get("table_name")
            for step in steps
            for table in step.get("target_tables", [])
            if isinstance(table, dict) and table.get("table_name")
        )
        upstream = _dedupe(raw_job.get("job_dependencies", {}).get("upstream_jobs", []))
        downstream = _dedupe(raw_job.get("job_dependencies", {}).get("downstream_jobs", []))
        user_code_count = sum(
            1
            for step in steps
            if step.get("user_written_code") or step.get("user_written_code_entries")
        )

        return {
            "job_id": str(raw_job.get("job_id")),
            "job_name": str(raw_job.get("job_name") or raw_job.get("job_id")),
            "folder_path": str(raw_job.get("primary_folder") or ""),
            "job_kind": "structured_job",
            "steps": [
                {
                    "step_id": step.get("step_id"),
                    "step_name": step.get("step_name"),
                    "step_kind": step.get("step_kind", "step"),
                }
                for step in steps
            ],
            "steps_count": len(steps),
            "transformations_count": sum(
                len(step.get("transformations", [])) for step in steps if isinstance(step, dict)
            ),
            "has_user_code": user_code_count > 0,
            "source_tables": source_tables,
            "target_tables": target_tables,
            "temp_tables": [],
            "source_tables_count": len(source_tables),
            "target_tables_count": len(target_tables),
            "temp_tables_count": 0,
            "source_columns_count": 0,
            "target_columns_count": 0,
            "step_kinds": _dedupe(step.get("step_kind", "step") for step in steps),
            "upstream_dependencies": upstream,
            "downstream_dependencies": downstream,
            "via_tables": [],
            "raw_domain": raw_job.get("domain"),
            "fan_in": len(upstream),
            "fan_out": len(downstream),
        }

    def _extract_profile_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        upstream = _dedupe(raw_job.get("upstream_dependencies", []))
        downstream = _dedupe(raw_job.get("downstream_dependencies", []))
        return {
            "job_id": str(raw_job.get("job_id")),
            "job_name": str(raw_job.get("job_name") or raw_job.get("job_id")),
            "folder_path": str((raw_job.get("sas_folder_paths") or [""])[0]),
            "job_kind": "profile_job",
            "steps": [
                {"step_id": None, "step_name": name, "step_kind": "step"}
                for name in raw_job.get("step_names", [])
            ],
            "steps_count": _safe_int(raw_job.get("steps"), len(raw_job.get("step_names", []))),
            "transformations_count": _safe_int(raw_job.get("column_lineage_edges")),
            "has_user_code": _safe_int(raw_job.get("user_written_code_entries")) > 0,
            "source_tables": _dedupe(raw_job.get("input_table_names", [])),
            "target_tables": _dedupe(raw_job.get("output_table_names", [])),
            "temp_tables": [],
            "source_tables_count": _safe_int(raw_job.get("input_tables")),
            "target_tables_count": _safe_int(raw_job.get("output_tables")),
            "temp_tables_count": 0,
            "source_columns_count": 0,
            "target_columns_count": 0,
            "step_kinds": ["step"] if raw_job.get("step_names") else [],
            "upstream_dependencies": upstream,
            "downstream_dependencies": downstream,
            "via_tables": [],
            "raw_domain": raw_job.get("domain"),
            "fan_in": len(upstream),
            "fan_out": len(downstream),
        }

    def _extract_generic_job(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        steps = raw_job.get("steps", [])
        upstream = _dedupe(raw_job.get("upstream_dependencies", []))
        downstream = _dedupe(raw_job.get("downstream_dependencies", []))
        return {
            "job_id": str(raw_job.get("job_id")),
            "job_name": str(raw_job.get("job_name") or raw_job.get("job_id")),
            "folder_path": str(raw_job.get("folder_path") or ""),
            "job_kind": str(raw_job.get("job_kind") or "generic_job"),
            "steps": steps if isinstance(steps, list) else [],
            "steps_count": _safe_int(raw_job.get("steps_count"), len(steps)),
            "transformations_count": _safe_int(raw_job.get("transformations_count")),
            "has_user_code": bool(raw_job.get("has_user_code")),
            "source_tables": _dedupe(raw_job.get("source_tables", [])),
            "target_tables": _dedupe(raw_job.get("target_tables", [])),
            "temp_tables": _dedupe(raw_job.get("temp_tables", [])),
            "source_tables_count": _safe_int(raw_job.get("source_tables_count")),
            "target_tables_count": _safe_int(raw_job.get("target_tables_count")),
            "temp_tables_count": _safe_int(raw_job.get("temp_tables_count")),
            "source_columns_count": _safe_int(raw_job.get("source_columns_count")),
            "target_columns_count": _safe_int(raw_job.get("target_columns_count")),
            "step_kinds": _dedupe(raw_job.get("step_kinds", [])),
            "upstream_dependencies": upstream,
            "downstream_dependencies": downstream,
            "via_tables": _dedupe(raw_job.get("via_tables", [])),
            "raw_domain": raw_job.get("domain"),
            "fan_in": len(upstream),
            "fan_out": len(downstream),
        }

    def _enrich_job(self, base_job: Dict[str, Any]) -> Dict[str, Any]:
        evidence = {"domain": [], "source_systems": [], "future_core": [], "overrides": []}
        assumptions: List[str] = []

        report_match = self.dw_index.job_index.get(base_job["job_id"], {})
        domain_info = self._infer_domain(base_job, report_match, evidence, assumptions)
        source_system_info = self._infer_source_systems(base_job, report_match, evidence, assumptions)
        future_core_info = self._infer_future_core(
            base_job,
            domain_info,
            source_system_info,
            evidence,
            assumptions,
        )
        analytical_model = self._infer_analytical_model(domain_info["domain"])
        similarity_score = self._analytical_model_score(analytical_model)
        deadline_month = self._infer_deadline_month(domain_info["domain"], source_system_info["source_systems"])
        override_info = self._apply_job_overrides(
            base_job,
            report_match,
            domain_info,
            source_system_info,
            future_core_info,
            evidence,
            assumptions,
        )

        complexity_rank = self._job_complexity_rank(base_job)
        business_priority = self._domain_priority(domain_info["domain"])
        overall_confidence = fmean(
            [
                domain_info["confidence"],
                source_system_info["confidence"],
                future_core_info["confidence"],
            ]
        )
        if override_info.get("confidence"):
            overall_confidence = fmean([overall_confidence, override_info["confidence"]])

        return {
            "job_id": base_job["job_id"],
            "job_name": base_job["job_name"],
            "folder_path": base_job["folder_path"],
            "job_kind": base_job["job_kind"],
            "domain": override_info.get("domain", domain_info["domain"]),
            "subcluster": override_info.get("subcluster", report_match.get("subcluster") or "Unknown"),
            "insurance_type": override_info.get(
                "insurance_type",
                report_match.get("insurance_type") or "Unknown",
            ),
            "source_systems": override_info.get("source_systems", source_system_info["source_systems"]),
            "future_core_candidate": override_info.get(
                "future_core_candidate",
                future_core_info["future_core_candidate"],
            ),
            "future_core_system": override_info.get(
                "future_core_system",
                future_core_info["future_core_system"],
            ),
            "steps": base_job["steps"],
            "steps_count": base_job["steps_count"],
            "transformations_count": base_job["transformations_count"],
            "has_user_code": base_job["has_user_code"],
            "source_tables": base_job["source_tables"],
            "target_tables": base_job["target_tables"],
            "temp_tables": base_job["temp_tables"],
            "step_kinds": base_job["step_kinds"],
            "job_dependencies": {
                "upstream": base_job["upstream_dependencies"],
                "downstream": base_job["downstream_dependencies"],
            },
            "upstream_dependencies": base_job["upstream_dependencies"],
            "downstream_dependencies": base_job["downstream_dependencies"],
            "lineage_signals": {
                "source_tables_count": base_job["source_tables_count"],
                "target_tables_count": base_job["target_tables_count"],
                "temp_tables_count": base_job["temp_tables_count"],
                "source_columns_count": base_job["source_columns_count"],
                "target_columns_count": base_job["target_columns_count"],
                "fan_in": len(base_job["upstream_dependencies"]),
                "fan_out": len(base_job["downstream_dependencies"]),
                "via_tables": base_job["via_tables"],
                "lineage_density": round(
                    (
                        base_job["source_tables_count"]
                        + base_job["target_tables_count"]
                        + len(base_job["upstream_dependencies"])
                        + len(base_job["downstream_dependencies"])
                    )
                    / max(1, base_job["steps_count"]),
                    4,
                ),
            },
            "complexity_indicators": {
                "complexity_rank": round(complexity_rank, 4),
                "step_breadth_rank": round(
                    _percentile_rank(
                        base_job["steps_count"],
                        self._job_feature_distributions.get("steps_count", []),
                    ),
                    4,
                ),
                "transformation_rank": round(
                    _percentile_rank(
                        base_job["transformations_count"],
                        self._job_feature_distributions.get("transformations_count", []),
                    ),
                    4,
                ),
            },
            "business_context": {
                "business_priority": override_info.get("business_priority", business_priority),
                "deadline_month": override_info.get("deadline_month", deadline_month),
                "analytical_model": analytical_model,
                "analytical_similarity_score": similarity_score,
            },
            "confidence": {
                "domain": round(domain_info["confidence"], 4),
                "source_systems": round(source_system_info["confidence"], 4),
                "future_core_candidate": round(future_core_info["confidence"], 4),
                "overall": round(_clamp(overall_confidence, 0.0, 1.0), 4),
            },
            "evidence": evidence,
            "assumptions": assumptions,
        }

    def _infer_domain(
        self,
        job: Dict[str, Any],
        report_match: Dict[str, Any],
        evidence: Dict[str, List[str]],
        assumptions: List[str],
    ) -> Dict[str, Any]:
        raw_domain = job.get("raw_domain")
        if raw_domain:
            evidence["domain"].append("raw_job.domain")
            return {"domain": str(raw_domain), "confidence": 0.95}

        if report_match.get("domain"):
            evidence["domain"].append(
                f"dw_report:{report_match.get('domain')}::{report_match.get('subcluster', 'Unknown')}"
            )
            return {"domain": str(report_match["domain"]), "confidence": 0.92}

        folder_text = f"{job.get('folder_path', '')} {job.get('job_name', '')}".lower()
        aliases = self.domain_taxonomy.get("aliases", {})
        for domain, patterns in aliases.items():
            for pattern in patterns:
                if pattern.lower() in folder_text:
                    evidence["domain"].append(f"folder_alias:{pattern}->{domain}")
                    return {"domain": domain, "confidence": 0.68}

        assumptions.append("Domain inferred as Unknown because no explicit or report-backed mapping was found.")
        evidence["domain"].append("fallback:Unknown")
        return {"domain": "Unknown", "confidence": 0.2}

    def _infer_source_systems(
        self,
        job: Dict[str, Any],
        report_match: Dict[str, Any],
        evidence: Dict[str, List[str]],
        assumptions: List[str],
    ) -> Dict[str, Any]:
        matched_systems = []
        match_confidence = 0.0
        haystack_parts = [
            job.get("folder_path", ""),
            job.get("job_name", ""),
            " ".join(job.get("source_tables", [])),
            " ".join(job.get("target_tables", [])),
            " ".join(job.get("via_tables", [])),
        ]
        for step in job.get("steps", []):
            haystack_parts.append(step.get("step_name") or "")
        haystack = " ".join(part for part in haystack_parts if part).lower()

        for rule in self.source_system_rules:
            patterns = [pattern.lower() for pattern in rule.get("patterns", [])]
            if any(pattern in haystack for pattern in patterns):
                matched_systems.append(rule["name"])
                evidence["source_systems"].append(f"pattern:{rule['name']}")
                match_confidence = max(match_confidence, 0.8)

        if not matched_systems and report_match.get("folder_path"):
            report_folder = report_match["folder_path"].lower()
            for rule in self.source_system_rules:
                patterns = [pattern.lower() for pattern in rule.get("patterns", [])]
                if any(pattern in report_folder for pattern in patterns):
                    matched_systems.append(rule["name"])
                    evidence["source_systems"].append(f"dw_report_folder:{rule['name']}")
                    match_confidence = max(match_confidence, 0.72)

        matched_systems = _dedupe(matched_systems)
        if not matched_systems:
            assumptions.append(
                "Source systems inferred as empty because no configured pattern matched this job."
            )
        return {
            "source_systems": matched_systems,
            "confidence": match_confidence if matched_systems else 0.25,
        }

    def _infer_future_core(
        self,
        job: Dict[str, Any],
        domain_info: Dict[str, Any],
        source_system_info: Dict[str, Any],
        evidence: Dict[str, List[str]],
        assumptions: List[str],
    ) -> Dict[str, Any]:
        future_core_by_domain = self.mode_eligibility_rules.get("future_core_by_domain", {})
        domain = domain_info["domain"]
        future_core_system = future_core_by_domain.get(domain)

        for source_rule in self.source_system_rules:
            if source_rule["name"] in source_system_info["source_systems"] and source_rule.get(
                "future_core_system"
            ):
                future_core_system = source_rule["future_core_system"]
                evidence["future_core"].append(
                    f"source_system_future_core:{source_rule['name']}->{future_core_system}"
                )

        if future_core_system:
            evidence["future_core"].append(f"domain_future_core:{domain}->{future_core_system}")
            return {
                "future_core_candidate": True,
                "future_core_system": future_core_system,
                "confidence": max(0.65, domain_info["confidence"]),
            }

        assumptions.append(
            "Future-core candidacy is low-confidence because the domain did not map to a configured target core."
        )
        return {
            "future_core_candidate": False,
            "future_core_system": None,
            "confidence": 0.35,
        }

    def _apply_job_overrides(
        self,
        job: Dict[str, Any],
        report_match: Dict[str, Any],
        domain_info: Dict[str, Any],
        source_system_info: Dict[str, Any],
        future_core_info: Dict[str, Any],
        evidence: Dict[str, List[str]],
        assumptions: List[str],
    ) -> Dict[str, Any]:
        override = {}
        combined_rules = [
            self.business_mapping.get("job_id_overrides", {}).get(job["job_id"]),
            self.roadmap_overrides.get("job_id_overrides", {}).get(job["job_id"]),
        ]
        for candidate in combined_rules:
            if isinstance(candidate, dict):
                override.update(candidate)

        folder_path = (job.get("folder_path") or report_match.get("folder_path") or "").lower()
        for rule in self.business_mapping.get("folder_rules", []):
            if not isinstance(rule, dict):
                continue
            pattern = str(rule.get("contains") or "").lower()
            if pattern and pattern in folder_path:
                override.update(rule.get("override", {}))
                evidence["overrides"].append(f"business_mapping.folder:{pattern}")

        subcluster = report_match.get("subcluster")
        if subcluster and subcluster in self.business_mapping.get("subcluster_rules", {}):
            override.update(self.business_mapping["subcluster_rules"][subcluster])
            evidence["overrides"].append(f"business_mapping.subcluster:{subcluster}")

        if override:
            assumptions.append("Business mapping or roadmap override rules adjusted one or more job attributes.")
        if "confidence" not in override and override:
            override["confidence"] = 0.98

        if "domain" not in override and domain_info["domain"] == "Unknown":
            fallback_domain = next(
                (
                    rule.get("default_domain")
                    for rule in self.source_system_rules
                    if rule["name"] in source_system_info["source_systems"] and rule.get("default_domain")
                ),
                None,
            )
            if fallback_domain:
                override["domain"] = fallback_domain
                evidence["overrides"].append(f"default_domain_from_source_system:{fallback_domain}")

        if "future_core_system" not in override and future_core_info["future_core_system"]:
            override["future_core_system"] = future_core_info["future_core_system"]
        if "future_core_candidate" not in override:
            override["future_core_candidate"] = future_core_info["future_core_candidate"]

        return override

    def _job_complexity_rank(self, job: Dict[str, Any]) -> float:
        step_rank = _percentile_rank(
            job.get("steps_count", 0),
            self._job_feature_distributions.get("steps_count", []),
        )
        transform_rank = _percentile_rank(
            job.get("transformations_count", 0),
            self._job_feature_distributions.get("transformations_count", []),
        )
        source_rank = _percentile_rank(
            job.get("source_tables_count", 0),
            self._job_feature_distributions.get("source_tables_count", []),
        )
        target_rank = _percentile_rank(
            job.get("target_tables_count", 0),
            self._job_feature_distributions.get("target_tables_count", []),
        )
        fan_in_rank = _percentile_rank(
            len(job.get("upstream_dependencies", [])),
            self._job_feature_distributions.get("fan_in", []),
        )
        fan_out_rank = _percentile_rank(
            len(job.get("downstream_dependencies", [])),
            self._job_feature_distributions.get("fan_out", []),
        )
        user_code_bonus = 1.0 if job.get("has_user_code") else 0.0
        return _clamp(
            (
                0.22 * step_rank
                + 0.28 * transform_rank
                + 0.12 * source_rank
                + 0.12 * target_rank
                + 0.12 * fan_in_rank
                + 0.09 * fan_out_rank
                + 0.05 * user_code_bonus
            ),
            0.0,
            1.0,
        )

    def _domain_priority(self, domain: str) -> float:
        domain_constraints = self.config.get("domain_constraints", {})
        if domain in domain_constraints:
            return _safe_float(domain_constraints[domain].get("priority_weight"), 0.8)
        default_weights = {
            "Claims": 1.0,
            "Entities": 0.95,
            "Policies": 0.9,
            "Unknown": 0.6,
        }
        return default_weights.get(domain, 0.75)

    def _infer_deadline_month(self, domain: str, source_systems: List[str]) -> Optional[int]:
        deadlines = []
        for source_system in source_systems:
            entry = self.config.get("system_deadlines", {}).get(source_system)
            if isinstance(entry, dict) and entry.get("deadline_month"):
                deadlines.append(_safe_int(entry["deadline_month"]))
        domain_deadline = self.config.get("domain_deadlines", {}).get(domain)
        if domain_deadline:
            deadlines.append(_safe_int(domain_deadline))
        deadlines = [deadline for deadline in deadlines if deadline > 0]
        return min(deadlines) if deadlines else None

    def _infer_analytical_model(self, domain: str) -> Optional[str]:
        domain_map = self.mode_eligibility_rules.get("analytical_model_domain_map", {})
        for model_name, mapped_domains in domain_map.items():
            if domain in mapped_domains:
                return model_name
        return None

    def _analytical_model_score(self, model_name: Optional[str]) -> Optional[float]:
        if not model_name:
            return None
        return self.similarity_scores.get(model_name, {}).get("overall_score")

    def _load_similarity_scores(
        self,
        similarity_scores_path: Optional[Path],
    ) -> Dict[str, Dict[str, Any]]:
        if not similarity_scores_path or not similarity_scores_path.exists():
            return {}

        payload = _load_json(similarity_scores_path)
        scores = {}
        for model_name, data in payload.items():
            overall_score = None
            if isinstance(data, dict):
                overall_score = _safe_float(data.get("overall_score"), 0.0)
                if overall_score <= 0:
                    overall_score = self._extract_score_from_sample_rows(data.get("sheets", []))
            if overall_score and overall_score > 0:
                scores[model_name] = {"overall_score": overall_score, "confidence": 0.8}
            else:
                scores[model_name] = {
                    "overall_score": 75.0,
                    "confidence": 0.5,
                    "assumption": "Similarity workbook exists but did not expose a machine-readable overall score.",
                }
        return scores

    @staticmethod
    def _extract_score_from_sample_rows(sheets: List[Dict[str, Any]]) -> Optional[float]:
        weighted_scores = []
        for sheet in sheets or []:
            for row in sheet.get("sample_data", []):
                if not isinstance(row, dict):
                    continue
                for key, value in row.items():
                    if "weighted score" in str(key).lower():
                        numeric = _safe_float(value, -1.0)
                        if numeric >= 0:
                            weighted_scores.append(numeric)
        if weighted_scores:
            return round(sum(weighted_scores), 2)
        return None


def _load_optional_mapping(path: Optional[Path]) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    payload = _load_json(path)
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize SAS metadata into the roadmap canonical schema.")
    parser.add_argument("input_path", help="Path to a jobs directory, JSON array, or JSONL file.")
    parser.add_argument("output_path", help="Path to the normalized_jobs.json output.")
    parser.add_argument("--config", dest="config_path", help="Optional optimizer config JSON.")
    parser.add_argument("--business-mapping", dest="business_mapping_path", help="Optional business mapping JSON.")
    parser.add_argument("--roadmap-overrides", dest="roadmap_overrides_path", help="Optional roadmap overrides JSON.")
    parser.add_argument("--dw-reports-dir", dest="dw_reports_dir", help="Optional directory containing *_DW_Report.txt files.")
    parser.add_argument("--similarity-scores", dest="similarity_scores_path", help="Optional similarity scores JSON.")
    parser.add_argument("--summary-output", dest="summary_output_path", help="Optional normalization summary JSON.")
    args = parser.parse_args()

    config = _load_optional_mapping(Path(args.config_path)) if args.config_path else {}
    business_mapping = _load_optional_mapping(Path(args.business_mapping_path)) if args.business_mapping_path else {}
    roadmap_overrides = _load_optional_mapping(Path(args.roadmap_overrides_path)) if args.roadmap_overrides_path else {}
    normalizer = SASMetadataNormalizer(
        config,
        business_mapping=business_mapping,
        roadmap_overrides=roadmap_overrides,
        report_dir=Path(args.dw_reports_dir) if args.dw_reports_dir else None,
        similarity_scores_path=Path(args.similarity_scores_path) if args.similarity_scores_path else None,
    )

    normalized_jobs = normalizer.normalize_jobs_from_source(Path(args.input_path))
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized_jobs, indent=2), encoding="utf-8")

    if args.summary_output_path:
        summary_path = Path(args.summary_output_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(normalizer.summarize_jobs(normalized_jobs), indent=2),
            encoding="utf-8",
        )

    print(f"Normalized {len(normalized_jobs)} jobs -> {output_path}")


if __name__ == "__main__":
    main()
