#!/usr/bin/env python3
"""
Main Execution Script for Chaos Injection and Mitigation Test
Orchestrates the complete test workflow using modular components.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import configuration and test modules
from nl_interface.anomalies.experiment_utils import (
    get_experiment_config, 
    get_alert_config, 
    get_logging_config,
    validate_config
)
from nl_interface.anomalies.chaos_mitigation import ChaosAndMitigationTest

def setup_logging():
    """Setup logging configuration."""
    log_config = get_logging_config()
    
    # Configure basic logging
    logging.basicConfig(
        level=getattr(logging, log_config["level"]),
        format=log_config["format"]
    )

    # Suppress verbose logs from specified libraries
    for lib in log_config["suppress_libs"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

def check_prerequisites():
    """Check that all prerequisites are met."""
    print("Checking prerequisites...")
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable must be set")
        return False
    
    # Validate configuration
    try:
        validate_config()
        print("Configuration validated")
    except ValueError as e:
        print(f"Configuration validation failed: {e}")
        return False
    
    return True

def print_experiment_info():
    """Print information about the experiment to be run."""
    config = get_experiment_config()
    
    print("CHAOS EXPERIMENT CONFIGURATION")
    print("=" * 40)
    print(f"Target: {config['target_app']} ({config['namespace']})")
    print(f"Chaos: {config['chaos_config']['fault_type']} ({config['chaos_config']['intensity']}, {config['chaos_duration']})")
    print(f"Duration: ~{config['monitoring_duration']//60} minutes")
    print(f"Agent: {config['agent_config']['openai_model']} (max {config['agent_config']['max_rounds']} rounds)")
    print("=" * 40)

async def run_experiment():
    """Run the complete chaos injection and mitigation experiment."""
    # Get configurations
    experiment_config = get_experiment_config()
    alert_config = get_alert_config()
    
    # Create test instance
    test = ChaosAndMitigationTest(experiment_config, alert_config)
    
    try:
        # Run the full experiment
        results = await test.run_full_experiment()
        return results
    except KeyboardInterrupt:
        print(f"\nExperiment interrupted! Performing emergency cleanup...")
        await test.emergency_cleanup()
        raise

def print_final_results(results):
    """Print final experiment results."""
    print(f"\nFINAL EXPERIMENT STATUS")
    print("=" * 40)
    
    if results.get("interrupted", False):
        print(f"Status: INTERRUPTED")
        print(f"Reason: {results['error']}")
        print(f"Completed phases: {', '.join(results['phases_completed'])}")
    elif results["success"]:
        print(f"Status: SUCCESS")
        print(f"Completed phases: {', '.join(results['phases_completed'])}")
        
        # Show phase metrics summary
        if results.get('phase_metrics'):
            print(f"\nPhase metrics collected:")
            for phase, metrics in results['phase_metrics'].items():
                print(f"  {phase}: {metrics['total_requests']} requests, {metrics['success_rate_percent']}% success")
        
        if results['agent_actions']:
            print(f"\nAgent took {len(results['agent_actions'])} action(s)")
    else:
        print(f"Status: FAILED")
        print(f"Error: {results['error']}")
        print(f"Completed phases: {', '.join(results['phases_completed'])}")
    
    print("=" * 40)

async def main():
    """Main execution function."""
    try:
        # Setup logging
        setup_logging()
        
        # Check prerequisites
        if not check_prerequisites():
            return 1
        
        # Print experiment information
        print_experiment_info()
        
        # Ask for confirmation
        print(f"\nThis experiment will deploy fresh apps, inject chaos, generate traffic,")
        print(f"and run AI agent mitigation for ~{get_experiment_config()['monitoring_duration']//60} minutes.")
        
        try:
            confirmation = input(f"\nProceed? (y/N): ").strip().lower()
            if confirmation not in ['y', 'yes']:
                print("Experiment cancelled")
                return 0
        except KeyboardInterrupt:
            print("\nExperiment cancelled")
            return 0
        
        # Run the experiment
        print(f"\nStarting experiment...")
        results = await run_experiment()
        
        # Print final results
        print_final_results(results)
        
        # Return appropriate exit code
        return 0 if results["success"] else 1
        
    except KeyboardInterrupt:
        print(f"\nExperiment interrupted (Ctrl+C)")
        print(f"Emergency cleanup completed")
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logging.exception("Unexpected error in main execution")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 