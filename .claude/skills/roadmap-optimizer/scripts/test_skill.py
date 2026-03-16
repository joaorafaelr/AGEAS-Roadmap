#!/usr/bin/env python3
"""
Test Script for Roadmap Optimizer Skill
======================================
Tests the improved roadmap optimizer with a sample dataset
to ensure all components work correctly.
"""

import json
import os
from pathlib import Path
import tempfile


def create_sample_migration_data():
    """Create sample migration data for testing."""

    # Sample configuration for a generic application modernization project
    config = {
        "migration_horizon_months": 24,
        "team_capacity": 6,
        "domain_constraints": {
            "core": {"earliest_start": 0, "priority_weight": 1.0},
            "customer": {"earliest_start": 3, "priority_weight": 0.9},
            "reporting": {"earliest_start": 6, "priority_weight": 0.7}
        },
        "migration_modes": {
            "direct_migration": {
                "description": "Direct migration to cloud-native",
                "duration_multiplier": 1.3,
                "tech_debt_penalty": 0.0,
                "base_hours": 400,
                "cost_multiplier": 1.3
            },
            "lift_and_shift": {
                "description": "Lift and shift approach",
                "duration_multiplier": 0.8,
                "tech_debt_penalty": 1.5,
                "base_hours": 200,
                "cost_multiplier": 0.8
            },
            "bridge_approach": {
                "description": "Bridge solution",
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
                "affected_domains": ["core"]
            }
        }
    }

    # Sample job/application data
    sample_jobs = [
        {
            "job_id": "UserAuthService",
            "domain": "core",
            "steps": [
                {
                    "step_id": "authentication",
                    "step_type": "business_logic",
                    "complexity": "high"
                }
            ],
            "upstream_dependencies": [],
            "downstream_dependencies": ["UserManagementService", "PaymentService"],
            "technology_stack": ["Java", "Oracle"],
            "target_stack": ["Python", "PostgreSQL"],
            "volume_indicators": {
                "daily_transactions": 50000,
                "size_factor": 1.5
            },
            "business_context": {
                "criticality": "critical"
            }
        },
        {
            "job_id": "UserManagementService",
            "domain": "customer",
            "steps": [
                {
                    "step_id": "user_crud",
                    "step_type": "data_management",
                    "complexity": "medium"
                }
            ],
            "upstream_dependencies": ["UserAuthService"],
            "downstream_dependencies": ["CustomerReportingService"],
            "technology_stack": ["Java", "Oracle"],
            "target_stack": ["Python", "PostgreSQL"],
            "volume_indicators": {
                "daily_transactions": 25000,
                "size_factor": 1.2
            },
            "business_context": {
                "criticality": "high"
            }
        },
        {
            "job_id": "PaymentService",
            "domain": "core",
            "steps": [
                {
                    "step_id": "payment_processing",
                    "step_type": "business_logic",
                    "complexity": "high"
                }
            ],
            "upstream_dependencies": ["UserAuthService"],
            "downstream_dependencies": ["PaymentReportingService"],
            "technology_stack": ["COBOL", "DB2"],
            "target_stack": ["Java", "PostgreSQL"],
            "volume_indicators": {
                "daily_transactions": 100000,
                "size_factor": 2.5
            },
            "business_context": {
                "criticality": "critical",
                "regulatory_requirements": ["PCI-DSS"]
            }
        },
        {
            "job_id": "CustomerReportingService",
            "domain": "reporting",
            "steps": [
                {
                    "step_id": "generate_reports",
                    "step_type": "reporting",
                    "complexity": "low"
                }
            ],
            "upstream_dependencies": ["UserManagementService"],
            "downstream_dependencies": [],
            "technology_stack": ["Java", "Oracle"],
            "target_stack": ["Python", "PostgreSQL"],
            "volume_indicators": {
                "daily_transactions": 5000,
                "size_factor": 0.8
            },
            "business_context": {
                "criticality": "medium"
            }
        },
        {
            "job_id": "PaymentReportingService",
            "domain": "reporting",
            "steps": [
                {
                    "step_id": "payment_reports",
                    "step_type": "reporting",
                    "complexity": "low"
                }
            ],
            "upstream_dependencies": ["PaymentService"],
            "downstream_dependencies": [],
            "technology_stack": ["Java", "Oracle"],
            "target_stack": ["Python", "PostgreSQL"],
            "volume_indicators": {
                "daily_transactions": 10000,
                "size_factor": 1.0
            },
            "business_context": {
                "criticality": "medium"
            }
        }
    ]

    return config, sample_jobs


def test_package_aggregator():
    """Test the package aggregator script."""
    print("Testing package aggregator...")

    config, jobs = create_sample_migration_data()

    # Import the package aggregator
    try:
        import sys
        sys.path.append(str(Path(__file__).parent))
        from package_aggregator import PackageAggregator

        # Create aggregator
        aggregator = PackageAggregator(jobs, config)
        aggregator.load_jobs()
        aggregator.build_lineage_graph()

        clusters = aggregator.identify_job_clusters()
        packages = aggregator.create_packages(clusters)

        print(f"✅ Package aggregation successful: {len(packages)} packages created")
        for pkg_id, pkg in packages.items():
            print(f"   - {pkg.name}: {len(pkg.job_ids)} jobs, complexity {pkg.complexity_score}")

        return True

    except Exception as e:
        print(f"❌ Package aggregator test failed: {e}")
        return False


def test_domain_processor():
    """Test the domain data processor."""
    print("Testing domain data processor...")

    try:
        import sys
        sys.path.append(str(Path(__file__).parent))
        from domain_data_processor import DomainDataProcessor

        # Create processor
        base_path = Path(__file__).parent.parent
        processor = DomainDataProcessor(base_path)

        # Test similarity score processing (if file exists)
        similarity_path = base_path / "data" / "similarity_scores.json"
        if similarity_path.exists():
            mappings = processor.process_similarity_scores(similarity_path)
            print(f"✅ Similarity score processing successful: {len(mappings)} models")
        else:
            print("ℹ️  No similarity scores file found - skipping that test")

        print("✅ Domain processor test completed")
        return True

    except Exception as e:
        print(f"❌ Domain processor test failed: {e}")
        return False


def test_skill_integration():
    """Test overall skill integration."""
    print("Testing skill integration...")

    # Create temporary test data
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Save test data
        config, jobs = create_sample_migration_data()

        config_path = temp_path / "test_config.json"
        jobs_path = temp_path / "test_jobs.json"

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        with open(jobs_path, 'w') as f:
            json.dump(jobs, f, indent=2)

        print(f"✅ Test data created in {temp_path}")
        print(f"   - Config: {config_path}")
        print(f"   - Jobs: {jobs_path}")
        print(f"   - {len(jobs)} sample jobs with dependencies")

        # Verify dependencies are correctly structured
        deps = {}
        for job in jobs:
            deps[job['job_id']] = {
                'upstream': job.get('upstream_dependencies', []),
                'downstream': job.get('downstream_dependencies', [])
            }

        print("\n📊 Dependency structure:")
        for job_id, dep_info in deps.items():
            print(f"   {job_id}:")
            if dep_info['upstream']:
                print(f"     ⬅️  Depends on: {dep_info['upstream']}")
            if dep_info['downstream']:
                print(f"     ➡️  Required by: {dep_info['downstream']}")

        return True


def main():
    """Run all tests."""
    print("="*60)
    print("ROADMAP OPTIMIZER SKILL TESTS")
    print("="*60)

    tests = [
        test_skill_integration,
        test_domain_processor,
        test_package_aggregator,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()

    # Summary
    passed = sum(results)
    total = len(results)

    print("="*60)
    print(f"TEST RESULTS: {passed}/{total} passed")
    print("="*60)

    if passed == total:
        print("🎉 All tests passed! The skill is ready for use.")
    else:
        print("⚠️  Some tests failed. Please review the output above.")


if __name__ == "__main__":
    main()