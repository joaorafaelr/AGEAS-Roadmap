#!/usr/bin/env python3
"""
Domain-Specific Data Processor
==============================
Processes the domain cluster reports (Claims, Entities, Policies) and similarity scores
to enhance package aggregation with business context and similarity metrics.

This integrates the specific cluster structures from DW reports with the
analytical model similarity scores (UNO, MAOC, MAE) to improve roadmap optimization.
"""

import re
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class DomainCluster:
    """Represents a domain cluster extracted from DW reports."""
    domain: str
    cluster_name: str
    insurance_type: Optional[str]  # Life, Non-Life, Both
    job_count: int
    total_steps: int
    source_tables: int
    target_tables: int
    complexity_indicators: Dict[str, Any]
    jobs: List[Dict[str, Any]]


@dataclass
class SimilarityMapping:
    """Represents similarity scores for analytical models."""
    model_name: str  # UNO, MAOC, or MAE
    overall_score: Optional[float]
    dimension_scores: Dict[str, float]
    mapping_confidence: str
    recommendations: List[str]


class DomainDataProcessor:
    """Processes domain-specific cluster reports and similarity scores."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.domain_clusters = {}
        self.similarity_mappings = {}

    def process_domain_reports(self, reports_path: Path) -> Dict[str, List[DomainCluster]]:
        """Process all domain DW reports."""
        results = {}

        report_files = {
            'Claims': 'Claims_DW_Report.txt',
            'Entities': 'Entities_DW_Report.txt',
            'Policies': 'Policies_DW_Report.txt'
        }

        for domain, filename in report_files.items():
            file_path = reports_path / filename
            if file_path.exists():
                print(f"Processing {domain} domain report...")
                results[domain] = self._parse_domain_report(file_path, domain)
            else:
                print(f"Warning: {filename} not found at {file_path}")

        return results

    def _parse_domain_report(self, file_path: Path, domain: str) -> List[DomainCluster]:
        """Parse a single domain report file."""
        clusters = []

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract domain summary
        domain_summary = self._extract_domain_summary(content)

        # Find cluster sections
        cluster_sections = self._split_into_cluster_sections(content)

        for section in cluster_sections:
            cluster = self._parse_cluster_section(section, domain)
            if cluster:
                clusters.append(cluster)

        return clusters

    def _extract_domain_summary(self, content: str) -> Dict[str, Any]:
        """Extract overall domain statistics."""
        summary = {}

        # Extract total jobs
        total_match = re.search(r'Total DW Jobs in \w+ domain:\s*(\d+)', content)
        if total_match:
            summary['total_jobs'] = int(total_match.group(1))

        # Extract insurance breakdown
        life_match = re.search(r'Life:\s*(\d+) jobs', content)
        nonlife_match = re.search(r'Non-Life:\s*(\d+) jobs', content)
        both_match = re.search(r'Both:\s*(\d+) jobs', content)

        if life_match or nonlife_match or both_match:
            summary['insurance_breakdown'] = {
                'Life': int(life_match.group(1)) if life_match else 0,
                'Non-Life': int(nonlife_match.group(1)) if nonlife_match else 0,
                'Both': int(both_match.group(1)) if both_match else 0
            }

        # Extract distinct sub-clusters count
        clusters_match = re.search(r'Distinct sub-clusters:\s*(\d+)', content)
        if clusters_match:
            summary['distinct_subclusters'] = int(clusters_match.group(1))

        return summary

    def _split_into_cluster_sections(self, content: str) -> List[str]:
        """Split content into individual cluster sections."""
        # Find cluster headers (Sub-cluster: Name (X jobs))
        cluster_pattern = r'Sub-cluster:\s+([^(]+)\s+\((\d+) jobs\)'
        sections = []

        matches = list(re.finditer(cluster_pattern, content))

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            sections.append(content[start:end])

        return sections

    def _parse_cluster_section(self, section: str, domain: str) -> Optional[DomainCluster]:
        """Parse an individual cluster section."""
        lines = section.strip().split('\n')

        # Extract cluster name and job count from header
        header_match = re.search(r'Sub-cluster:\s+([^(]+)\s+\((\d+) jobs\)', section)
        if not header_match:
            return None

        cluster_name = header_match.group(1).strip()
        job_count = int(header_match.group(2))

        # Extract insurance type context
        insurance_type = None
        if 'INSURANCE TYPE: LIFE' in section:
            insurance_type = 'Life'
        elif 'INSURANCE TYPE: NON-LIFE' in section:
            insurance_type = 'Non-Life'
        elif 'INSURANCE TYPE: BOTH' in section:
            insurance_type = 'Both'

        # Parse summary statistics
        complexity_indicators = self._extract_complexity_indicators(section)

        # Parse individual jobs
        jobs = self._parse_jobs_in_section(section)

        return DomainCluster(
            domain=domain,
            cluster_name=cluster_name,
            insurance_type=insurance_type,
            job_count=job_count,
            total_steps=complexity_indicators.get('total_steps', 0),
            source_tables=complexity_indicators.get('source_tables', 0),
            target_tables=complexity_indicators.get('target_tables', 0),
            complexity_indicators=complexity_indicators,
            jobs=jobs
        )

    def _extract_complexity_indicators(self, section: str) -> Dict[str, Any]:
        """Extract complexity metrics from cluster summary."""
        indicators = {}

        # Common patterns for metrics
        patterns = {
            'total_steps': r'Total steps:\s*(\d+)',
            'source_tables': r'Source tables:\s*(\d+)',
            'target_tables': r'Target tables:\s*(\d+)',
            'source_columns': r'Source columns:\s*(\d+)',
            'target_columns': r'Target columns:\s*(\d+)',
            'transformations': r'Transformations:\s*(\d+)',
            'temp_tables': r'Temp tables:\s*(\d+)',
            'jobs_with_user_code': r'Jobs with user code:\s*(\d+)',
            'jobs_with_upstream': r'Jobs with upstream:\s*(\d+)',
            'jobs_with_downstream': r'Jobs with downstream:\s*(\d+)'
        }

        for metric, pattern in patterns.items():
            match = re.search(pattern, section)
            if match:
                indicators[metric] = int(match.group(1))

        return indicators

    def _parse_jobs_in_section(self, section: str) -> List[Dict[str, Any]]:
        """Extract individual job details from a cluster section."""
        jobs = []

        # Find job entries [001], [002], etc.
        job_pattern = r'\[(\d+)\]\s+([^\n]+)'
        job_matches = re.finditer(job_pattern, section)

        for match in job_matches:
            job_num = match.group(1)
            job_name = match.group(2).strip()

            # Extract job details following the header
            job_start = match.end()
            job_end = section.find(f'[{int(job_num):03d}]', job_start)
            if job_end == -1:
                job_end = len(section)

            job_section = section[job_start:job_end]

            job_details = self._parse_job_details(job_section, job_name)
            if job_details:
                jobs.append(job_details)

        return jobs

    def _parse_job_details(self, job_section: str, job_name: str) -> Dict[str, Any]:
        """Parse details of a single job."""
        details = {
            'job_name': job_name,
            'job_id': None,
            'folder': None,
            'steps': [],
            'upstream_jobs': [],
            'downstream_jobs': [],
            'complexity_metrics': {}
        }

        # Extract specific patterns
        patterns = {
            'job_id': r'Job ID:\s*([^\n]+)',
            'folder': r'Folder:\s*([^\n]+)',
            'steps_count': r'Steps:\s*(\d+)',
            'has_user_code': r'Has user code:\s*([^\n]+)',
            'source_columns': r'Source columns:\s*(\d+)',
            'target_columns': r'Target columns:\s*(\d+)',
            'transformations': r'Transformations:\s*(\d+)'
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, job_section)
            if match:
                value = match.group(1).strip()
                if field in ['steps_count', 'source_columns', 'target_columns', 'transformations']:
                    details['complexity_metrics'][field] = int(value)
                else:
                    details[field] = value

        # Extract upstream/downstream dependencies
        upstream_match = re.search(r'Upstream jobs:\s*([^\n]+)', job_section)
        if upstream_match:
            upstream_text = upstream_match.group(1)
            details['upstream_jobs'] = [job.strip() for job in upstream_text.split(',') if job.strip()]

        downstream_match = re.search(r'Downstream jobs:\s*([^\n]+)', job_section)
        if downstream_match:
            downstream_text = downstream_match.group(1)
            details['downstream_jobs'] = [job.strip() for job in downstream_text.split(',') if job.strip()]

        return details

    def process_similarity_scores(self, similarity_file: Path) -> Dict[str, SimilarityMapping]:
        """Process similarity scores from JSON file."""
        if not similarity_file.exists():
            print(f"Similarity scores file not found: {similarity_file}")
            return {}

        with open(similarity_file, 'r') as f:
            data = json.load(f)

        mappings = {}

        for model_name, model_data in data.items():
            if 'error' in model_data:
                print(f"Error processing {model_name}: {model_data['error']}")
                continue

            # Process each sheet to extract meaningful similarity data
            mapping = self._extract_similarity_mapping(model_name, model_data)
            if mapping:
                mappings[model_name] = mapping

        return mappings

    def _extract_similarity_mapping(self, model_name: str, model_data: Dict) -> Optional[SimilarityMapping]:
        """Extract meaningful similarity mapping from model data."""
        sheets = model_data.get('sheets', [])
        if not sheets:
            return None

        # Look for the main similarity mapping sheet
        main_sheet = None
        for sheet in sheets:
            if 'similarity' in sheet.get('name', '').lower() or 'mapping' in sheet.get('name', '').lower():
                main_sheet = sheet
                break

        if not main_sheet:
            main_sheet = sheets[0]  # Fallback to first sheet

        # Extract dimension scores and overall metrics
        dimension_scores = {}
        overall_score = None

        # Look for score columns with statistics
        for key, value in main_sheet.items():
            if key.endswith('_stats') and isinstance(value, dict):
                score_name = key.replace('_stats', '')
                if 'mean' in value and value['mean'] is not None:
                    dimension_scores[score_name] = value['mean']

        # Calculate overall score as average of dimensions
        if dimension_scores:
            overall_score = sum(dimension_scores.values()) / len(dimension_scores)

        return SimilarityMapping(
            model_name=model_name,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            mapping_confidence="medium",  # Default - could be enhanced
            recommendations=[]  # Could be extracted from sample data
        )

    def generate_enhanced_config(self, output_path: Path) -> Dict[str, Any]:
        """Generate an enhanced configuration incorporating domain-specific data."""
        config = {
            "migration_horizon_months": 60,
            "team_capacity": 6,
            "domain_clusters": {},
            "analytical_models": {},
            "business_rules": self._generate_business_rules()
        }

        # Add domain cluster information
        for domain, clusters in self.domain_clusters.items():
            config["domain_clusters"][domain] = []
            for cluster in clusters:
                config["domain_clusters"][domain].append({
                    "cluster_name": cluster.cluster_name,
                    "job_count": cluster.job_count,
                    "complexity_score": self._calculate_cluster_complexity(cluster),
                    "insurance_type": cluster.insurance_type,
                    "dependencies": self._extract_cluster_dependencies(cluster)
                })

        # Add similarity mapping information
        for model_name, mapping in self.similarity_mappings.items():
            config["analytical_models"][model_name] = asdict(mapping)

        # Save configuration
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)

        return config

    def _calculate_cluster_complexity(self, cluster: DomainCluster) -> float:
        """Calculate a complexity score for a cluster based on its metrics."""
        indicators = cluster.complexity_indicators

        # Weight different complexity factors
        complexity_score = (
            indicators.get('transformations', 0) * 0.3 +
            indicators.get('total_steps', 0) * 0.2 +
            indicators.get('source_tables', 0) * 0.15 +
            indicators.get('target_tables', 0) * 0.15 +
            indicators.get('jobs_with_user_code', 0) * 0.2
        )

        # Normalize by job count
        if cluster.job_count > 0:
            complexity_score /= cluster.job_count

        return round(complexity_score, 2)

    def _extract_cluster_dependencies(self, cluster: DomainCluster) -> Dict[str, List[str]]:
        """Extract dependencies between jobs within a cluster."""
        upstream_clusters = set()
        downstream_clusters = set()

        for job in cluster.jobs:
            upstream_clusters.update(job.get('upstream_jobs', []))
            downstream_clusters.update(job.get('downstream_jobs', []))

        return {
            "upstream_external": list(upstream_clusters),
            "downstream_external": list(downstream_clusters)
        }

    def _generate_business_rules(self) -> Dict[str, Any]:
        """Generate business rules based on domain analysis."""
        return {
            "strategic_approach_domains": ["Claims", "Entities", "Policies"],
            "foundational_clusters": {
                "Entities": "Entity Dimensions",
                "Policies": "Policy Core",
                "Claims": "Claims Core"
            },
            "parallel_limits": {
                "strategic_clusters_max": 2,
                "total_active_max": 4
            },
            "decommission_deadlines": {
                "CCS": "2026-Q3",
                "Tecnisys": "2028-Q3",
                "Cogen": "2028-Q3"
            }
        }


def main():
    """Main execution function."""
    base_path = Path(__file__).parent.parent

    # Set up paths - check multiple locations for the reports
    possible_reports_paths = [
        base_path.parent / "domain_data" / "cluster_reports",
        base_path.parent,  # Check parent directory directly
        Path.cwd(),  # Current working directory
    ]

    reports_path = None
    for path in possible_reports_paths:
        if path.exists() and any(str(f).endswith('DW_Report.txt') for f in path.iterdir() if f.is_file()):
            reports_path = path
            break

    if not reports_path:
        print("Warning: Could not find domain DW report files. Checked:")
        for path in possible_reports_paths:
            print(f"  {path} - exists: {path.exists()}")
        reports_path = base_path.parent  # Default fallback

    similarity_path = base_path / "data" / "similarity_scores.json"
    output_path = base_path / "data" / "enhanced_config.json"

    # Create processor
    processor = DomainDataProcessor(base_path)

    print(f"Processing domain cluster reports from: {reports_path}")
    processor.domain_clusters = processor.process_domain_reports(reports_path)

    print(f"\nProcessing similarity scores from {similarity_path}...")
    processor.similarity_mappings = processor.process_similarity_scores(similarity_path)

    print(f"\nGenerating enhanced configuration...")
    config = processor.generate_enhanced_config(output_path)

    # Print summary
    print("\n" + "="*60)
    print("DOMAIN DATA PROCESSING SUMMARY")
    print("="*60)

    for domain, clusters in processor.domain_clusters.items():
        print(f"\n{domain} Domain:")
        print(f"  Total clusters: {len(clusters)}")
        total_jobs = sum(cluster.job_count for cluster in clusters)
        print(f"  Total jobs: {total_jobs}")

        if clusters:
            avg_complexity = sum(processor._calculate_cluster_complexity(cluster) for cluster in clusters) / len(clusters)
            print(f"  Average complexity: {avg_complexity:.2f}")

    print(f"\nAnalytical Models:")
    for model_name, mapping in processor.similarity_mappings.items():
        print(f"  {model_name}: {mapping.overall_score:.1f}%" if mapping.overall_score else f"  {model_name}: No scores")

    print(f"\nEnhanced configuration saved to: {output_path}")


if __name__ == "__main__":
    main()