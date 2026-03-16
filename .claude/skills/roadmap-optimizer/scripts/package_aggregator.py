#!/usr/bin/env python3
"""
Package Aggregation Engine
Aggregates SAS jobs into logical migration packages using lineage analysis.
"""

import json
import pandas as pd
import networkx as nx
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

@dataclass
class JobInfo:
    job_id: str
    domain: str
    steps: List[Dict]
    upstream_deps: List[str]
    downstream_deps: List[str]
    complexity_score: float
    estimated_effort_days: float

@dataclass
class MigrationPackage:
    package_id: str
    name: str
    domain: str
    job_ids: List[str]
    total_effort_days: float
    complexity_score: float
    upstream_packages: List[str]
    downstream_packages: List[str]
    centrality_score: float
    business_value: float
    risk_score: float

class PackageAggregator:
    def __init__(self, jobs_data: List[Dict], config: Dict):
        self.jobs_data = jobs_data
        self.config = config
        self.jobs = {}
        self.lineage_graph = nx.DiGraph()
        self.packages = {}

    def load_jobs(self) -> None:
        """Parse job JSON data into JobInfo objects."""
        for job_data in self.jobs_data:
            job = JobInfo(
                job_id=job_data['job_id'],
                domain=job_data.get('domain', 'unknown'),
                steps=job_data.get('steps', []),
                upstream_deps=job_data.get('upstream_dependencies', []),
                downstream_deps=job_data.get('downstream_dependencies', []),
                complexity_score=self._calculate_complexity(job_data),
                estimated_effort_days=self._estimate_effort(job_data)
            )
            self.jobs[job.job_id] = job

    def build_lineage_graph(self) -> None:
        """Build networkx graph from job dependencies."""
        # Add nodes
        for job_id in self.jobs:
            self.lineage_graph.add_node(job_id)

        # Add edges
        for job in self.jobs.values():
            for upstream_id in job.upstream_deps:
                if upstream_id in self.jobs:
                    self.lineage_graph.add_edge(upstream_id, job.job_id)

    def identify_job_clusters(self) -> Dict[str, List[str]]:
        """Identify strongly connected components and business clusters."""
        clusters = {}

        # Find strongly connected components
        scc_components = list(nx.strongly_connected_components(self.lineage_graph))

        # Group by domain and connectivity
        domain_clusters = {}
        for job_id in self.jobs:
            domain = self.jobs[job_id].domain
            if domain not in domain_clusters:
                domain_clusters[domain] = []
            domain_clusters[domain].append(job_id)

        # Merge SCC and domain clustering
        cluster_id = 0
        for scc in scc_components:
            if len(scc) > 1:  # Multi-job components
                clusters[f"scc_{cluster_id}"] = list(scc)
                cluster_id += 1

        # Add domain-based clusters for remaining jobs
        processed_jobs = set()
        for cluster_jobs in clusters.values():
            processed_jobs.update(cluster_jobs)

        for domain, domain_jobs in domain_clusters.items():
            unprocessed = [j for j in domain_jobs if j not in processed_jobs]
            if unprocessed:
                # Further cluster by shared dependencies
                subclusters = self._cluster_by_dependencies(unprocessed)
                for i, subcluster in enumerate(subclusters):
                    clusters[f"{domain}_cluster_{i}"] = subcluster
                    processed_jobs.update(subcluster)

        return clusters

    def _cluster_by_dependencies(self, job_ids: List[str]) -> List[List[str]]:
        """Cluster jobs by shared dependencies within a domain."""
        if len(job_ids) <= 3:  # Small groups stay together
            return [job_ids]

        # Create similarity matrix based on shared dependencies
        n = len(job_ids)
        similarity = np.zeros((n, n))

        for i, job1 in enumerate(job_ids):
            for j, job2 in enumerate(job_ids):
                if i != j:
                    shared_upstream = len(set(self.jobs[job1].upstream_deps) &
                                        set(self.jobs[job2].upstream_deps))
                    shared_downstream = len(set(self.jobs[job1].downstream_deps) &
                                          set(self.jobs[job2].downstream_deps))
                    similarity[i][j] = shared_upstream + shared_downstream

        # Simple clustering: group jobs with high similarity
        clusters = []
        used = set()

        for i, job_id in enumerate(job_ids):
            if job_id in used:
                continue

            cluster = [job_id]
            used.add(job_id)

            # Add similar jobs to cluster
            for j, other_job in enumerate(job_ids):
                if other_job not in used and similarity[i][j] > 2:
                    cluster.append(other_job)
                    used.add(other_job)

            clusters.append(cluster)

        return clusters

    def create_packages(self, clusters: Dict[str, List[str]]) -> None:
        """Create MigrationPackage objects from job clusters."""
        for cluster_id, job_ids in clusters.items():
            # Calculate package-level metrics
            total_effort = sum(self.jobs[job_id].estimated_effort_days for job_id in job_ids)
            avg_complexity = np.mean([self.jobs[job_id].complexity_score for job_id in job_ids])

            # Determine dominant domain
            domains = [self.jobs[job_id].domain for job_id in job_ids]
            dominant_domain = max(set(domains), key=domains.count)

            # Calculate package dependencies
            all_upstream = set()
            all_downstream = set()

            for job_id in job_ids:
                all_upstream.update(self.jobs[job_id].upstream_deps)
                all_downstream.update(self.jobs[job_id].downstream_deps)

            # Remove internal dependencies
            upstream_packages = all_upstream - set(job_ids)
            downstream_packages = all_downstream - set(job_ids)

            # Calculate centrality in the overall graph
            centrality_scores = nx.betweenness_centrality(self.lineage_graph)
            package_centrality = np.mean([centrality_scores.get(job_id, 0) for job_id in job_ids])

            # Estimate business value and risk
            business_value = self._calculate_business_value(job_ids, dominant_domain)
            risk_score = self._calculate_risk_score(job_ids, total_effort, avg_complexity)

            package = MigrationPackage(
                package_id=cluster_id,
                name=self._generate_package_name(job_ids, dominant_domain),
                domain=dominant_domain,
                job_ids=job_ids,
                total_effort_days=total_effort,
                complexity_score=avg_complexity,
                upstream_packages=list(upstream_packages),
                downstream_packages=list(downstream_packages),
                centrality_score=package_centrality,
                business_value=business_value,
                risk_score=risk_score
            )

            self.packages[cluster_id] = package

    def _calculate_complexity(self, job_data: Dict) -> float:
        """Calculate complexity score for a job."""
        base_score = 1.0

        # Add complexity based on number of steps
        steps_score = len(job_data.get('steps', [])) * 0.2

        # Add complexity based on dependencies
        dep_score = (len(job_data.get('upstream_dependencies', [])) +
                    len(job_data.get('downstream_dependencies', []))) * 0.1

        # Add complexity based on data sources
        source_score = len(job_data.get('source_systems', [])) * 0.3

        return base_score + steps_score + dep_score + source_score

    def _estimate_effort(self, job_data: Dict) -> float:
        """Estimate effort in days for a job."""
        base_effort = 5.0  # Base 5 days per job

        # Scale by complexity
        complexity_factor = self._calculate_complexity(job_data) / 2.0

        # Scale by data volume indicators
        volume_factor = 1.0
        if 'volume_indicators' in job_data:
            volume_factor = min(3.0, job_data['volume_indicators'].get('size_factor', 1.0))

        return base_effort * complexity_factor * volume_factor

    def _calculate_business_value(self, job_ids: List[str], domain: str) -> float:
        """Calculate business value score for a package."""
        # Domain-based scoring
        domain_values = {
            'customer': 0.9,
            'product': 0.8,
            'claims': 0.85,
            'finance': 0.7,
            'operations': 0.6
        }

        base_value = domain_values.get(domain.lower(), 0.5)

        # Adjust for package size (economies of scale)
        size_factor = min(1.5, 1.0 + len(job_ids) / 100)

        return base_value * size_factor

    def _calculate_risk_score(self, job_ids: List[str], total_effort: float,
                            avg_complexity: float) -> float:
        """Calculate risk score for a package."""
        # Base risk from effort and complexity
        effort_risk = min(1.0, total_effort / 100)  # Risk increases with effort
        complexity_risk = min(1.0, avg_complexity / 5)  # Risk increases with complexity

        # Risk from dependencies
        total_deps = 0
        for job_id in job_ids:
            job = self.jobs[job_id]
            total_deps += len(job.upstream_deps) + len(job.downstream_deps)

        dependency_risk = min(1.0, total_deps / (len(job_ids) * 10))

        return (effort_risk + complexity_risk + dependency_risk) / 3

    def _generate_package_name(self, job_ids: List[str], domain: str) -> str:
        """Generate a meaningful name for a package."""
        # Try to extract common patterns from job names
        job_names = [self.jobs[job_id].job_id for job_id in job_ids]

        # Simple heuristic: find common prefixes/suffixes
        if len(job_names) > 1:
            common_prefix = self._find_common_prefix(job_names)
            if len(common_prefix) > 3:
                return f"{domain.title()} {common_prefix.title()} Package"

        return f"{domain.title()} Package {len(job_ids)} Jobs"

    def _find_common_prefix(self, strings: List[str]) -> str:
        """Find common prefix among strings."""
        if not strings:
            return ""

        prefix = strings[0]
        for string in strings[1:]:
            while not string.startswith(prefix) and prefix:
                prefix = prefix[:-1]

        return prefix.rstrip('_-.')

    def run_aggregation(self) -> Dict[str, MigrationPackage]:
        """Execute the full aggregation pipeline."""
        print("Loading jobs...")
        self.load_jobs()
        print(f"Loaded {len(self.jobs)} jobs")

        print("Building lineage graph...")
        self.build_lineage_graph()
        print(f"Graph has {self.lineage_graph.number_of_nodes()} nodes, "
              f"{self.lineage_graph.number_of_edges()} edges")

        print("Identifying clusters...")
        clusters = self.identify_job_clusters()
        print(f"Found {len(clusters)} clusters")

        print("Creating packages...")
        self.create_packages(clusters)
        print(f"Created {len(self.packages)} migration packages")

        return self.packages

    def export_packages(self, output_path: str) -> None:
        """Export packages to JSON file."""
        package_data = []
        for package in self.packages.values():
            package_data.append({
                'package_id': package.package_id,
                'name': package.name,
                'domain': package.domain,
                'job_count': len(package.job_ids),
                'total_effort_days': package.total_effort_days,
                'complexity_score': package.complexity_score,
                'upstream_count': len(package.upstream_packages),
                'downstream_count': len(package.downstream_packages),
                'centrality_score': package.centrality_score,
                'business_value': package.business_value,
                'risk_score': package.risk_score,
                'job_ids': package.job_ids
            })

        with open(output_path, 'w') as f:
            json.dump(package_data, f, indent=2)

        print(f"Packages exported to {output_path}")

if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 3:
        print("Usage: python package_aggregator.py <jobs_dir> <output_file>")
        sys.exit(1)

    jobs_dir = Path(sys.argv[1])
    output_file = sys.argv[2]

    # Load all job JSON files
    jobs_data = []
    for json_file in jobs_dir.glob("*.json"):
        with open(json_file) as f:
            jobs_data.append(json.load(f))

    # Default configuration
    config = {
        "max_package_size": 50,
        "min_package_size": 3,
        "domain_weights": {
            "customer": 1.0,
            "product": 0.9,
            "claims": 0.95,
            "finance": 0.8,
            "operations": 0.7
        }
    }

    # Run aggregation
    aggregator = PackageAggregator(jobs_data, config)
    packages = aggregator.run_aggregation()

    # Export results
    aggregator.export_packages(output_file)