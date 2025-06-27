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
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

# Import configuration and test modules
from .experiment_config import (
    get_experiment_config, 
    get_alert_config, 
    get_logging_config,
    validate_config
)
from .chaos_mitigation import ChaosAndMitigationTest

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
    print("🔍 Checking prerequisites...")
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable must be set")
        print("   Please set it in your .env file or export it in your shell")
        return False
    
    # Validate configuration
    try:
        validate_config()
        print("✅ Configuration validation passed")
    except ValueError as e:
        print(f"❌ Configuration validation failed: {e}")
        return False
    
    print("✅ All prerequisites met")
    return True

def print_experiment_info():
    """Print information about the experiment to be run."""
    config = get_experiment_config()
    
    print("🚀 CHAOS INJECTION AND MITIGATION EXPERIMENT")
    print("=" * 60)
    print(f"Target Application: {config['target_app']}")
    print(f"Namespace: {config['namespace']}")
    print(f"Chaos Type: {config['chaos_config']['fault_type']} ({config['chaos_config']['intensity']} intensity)")
    print(f"Chaos Duration: {config['chaos_duration']}")
    print(f"Total Test Duration: ~{config['monitoring_duration']}s ({config['monitoring_duration']//60} minutes)")
    print(f"Traffic Endpoints: {len(config['traffic_config']['endpoints'])}")
    print(f"Agent Model: {config['agent_config']['openai_model']}")
    print(f"Agent Max Rounds: {config['agent_config']['max_rounds']}")
    print("=" * 60)

async def run_experiment():
    """Run the complete chaos injection and mitigation experiment."""
    # Get configurations
    experiment_config = get_experiment_config()
    alert_config = get_alert_config()
    
    # Create test instance
    test = ChaosAndMitigationTest(experiment_config, alert_config)
    
    # Run the full experiment
    results = await test.run_full_experiment()
    
    return results

def print_final_results(results):
    """Print final experiment results."""
    print(f"\n🏆 FINAL EXPERIMENT RESULTS")
    print("=" * 50)
    
    if results["success"]:
        print(f"✅ Experiment Status: SUCCESS")
        print(f"📊 Phases Completed: {len(results['phases_completed'])}")
        for i, phase in enumerate(results['phases_completed'], 1):
            print(f"   {i}. {phase.replace('_', ' ').title()}")
        
        print(f"🤖 Agent Actions: {len(results['agent_actions'])}")
        if results['agent_actions']:
            for i, action in enumerate(results['agent_actions'], 1):
                print(f"   {i}. {action}")
    else:
        print(f"❌ Experiment Status: FAILED")
        print(f"💥 Error: {results['error']}")
        print(f"📊 Phases Completed: {len(results['phases_completed'])}")
        for i, phase in enumerate(results['phases_completed'], 1):
            print(f"   {i}. {phase.replace('_', ' ').title()}")
    
    print("=" * 50)

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
        print(f"\n⚠️  This experiment will:")
        print(f"   • Deploy fresh application instances")
        print(f"   • Inject extreme CPU stress chaos")
        print(f"   • Generate traffic for performance measurement")
        print(f"   • Deploy AI agent for automatic mitigation")
        print(f"   • Run for approximately {get_experiment_config()['monitoring_duration']//60} minutes")
        
        try:
            confirmation = input(f"\n🤔 Do you want to proceed? (y/N): ").strip().lower()
            if confirmation not in ['y', 'yes']:
                print("❌ Experiment cancelled by user")
                return 0
        except KeyboardInterrupt:
            print("\n❌ Experiment cancelled by user")
            return 0
        
        # Run the experiment
        print(f"\n🚀 Starting experiment...")
        results = await run_experiment()
        
        # Print final results
        print_final_results(results)
        
        # Return appropriate exit code
        return 0 if results["success"] else 1
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Experiment interrupted by user")
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        logging.exception("Unexpected error in main execution")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 