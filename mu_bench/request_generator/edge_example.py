"""
Practical Edge Computing Example

This example shows how to use the simplified EdgeRequestGenerator with
real edge infrastructure endpoints that match the user's actual setup.
"""
import logging
from mu_bench.request_generator.edge_request_generator import EdgeRequestGenerator
from mu_bench.request_generator.edge_calculator import EdgeTrafficCalculator


def get_real_edge_config():
    return {
        "base_host": "172.23.0.5",
        "apps": [
            {
                "name": "app-1",
                "port": 31116,
                "traffic_weight": 1.0,
                "wait_time": {"min": 0.5, "max": 2.0}
            },
            {
                "name": "app-2", 
                "port": 31115,
                "traffic_weight": 0.8,
                "wait_time": {"min": 1.0, "max": 3.0}
            }
        ],
        "edge_sites": {
            "edge-site-1": {
                "pattern": "urban_peak",
                "description": "Primary urban edge site",
                "traffic_weight": 1.0
            },
            "edge-site-2": {
                "pattern": "suburban_steady",
                "description": "Secondary suburban edge site", 
                "traffic_weight": 0.7
            }
        }
    }


def run_edge_load_test():
    """Run a realistic edge computing load test."""
    print("🌐 Starting Edge Computing Load Test")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("EdgeTest")
    
    # Get configuration
    config = get_real_edge_config()
    
    # Show what will be tested
    print(f"🏭 Testing {len(config['apps'])} edge apps on {config['base_host']}")
    print("🔌 Edge Applications (Port-Based):")
    for app in config['apps']:
        print(f"   • Port {app['port']}: {app['name']} (weight: {app['traffic_weight']})")
    
    print("🌍 Edge Sites:")
    for site_id, site_config in config['edge_sites'].items():
        print(f"   • {site_id}: {site_config['description']} ({site_config['pattern']})")
    
    print("\n🎯 Generated Endpoints (Port:Path format):")
    for app in config['apps']:
        for site_id in config['edge_sites'].keys():
            url = f"http://{config['base_host']}:{app['port']}/s0-{site_id}"
            print(f"   • {url}")
    
    print("\n🚀 Starting load test...")
    print("📊 Statistics will show as 'Port:/s0-edge-site' format")
    
    # Run the experiment
    generator = EdgeRequestGenerator(logger=logger)
    
    success = generator.run_edge_experiment(
        edge_config=config,
        max_users=15,
        spawn_rate=3,
        run_duration_seconds=120,  # 2 minutes
        simulated_period_seconds=3600,  # Simulate 1 hour
        log_level="INFO"
    )
    
    if success:
        print("\n✅ Edge load test completed successfully!")
        
        # Show final stats
        stats = generator.get_stats()
        if stats:
            print(f"📊 Final Results:")
            print(f"   Total Requests: {stats['total_requests']}")
            print(f"   Requests/Second: {stats['requests_per_second']:.2f}")
            print(f"   Average Response Time: {stats['average_response_time']:.2f}ms")
            print(f"   Failure Rate: {stats['failure_rate']:.2%}")
    else:
        print("\n❌ Edge load test failed!")


def demonstrate_traffic_patterns():
    """Demonstrate how different edge sites have different traffic patterns."""
    print("\n🕐 Edge Site Traffic Patterns Over 24 Hours:")
    print("=" * 50)
    
    calculator = EdgeTrafficCalculator()
    
    # Test different times of day
    times = [
        (0, "Midnight"),
        (6, "6 AM"),
        (9, "9 AM (Morning Peak)"),
        (12, "Noon"),
        (15, "3 PM (Afternoon Peak)"),
        (18, "6 PM (Evening)"),
        (22, "10 PM")
    ]
    
    sites = ["urban_peak", "suburban_steady", "rural_minimal", "industrial_shift"]
    
    print(f"{'Time':<20} {'Urban':<8} {'Suburban':<10} {'Rural':<8} {'Industrial':<12}")
    print("-" * 60)
    
    for hour, time_label in times:
        time_seconds = hour * 3600
        multipliers = []
        
        for site_pattern in sites:
            multiplier = calculator.calculate_site_traffic_multiplier(site_pattern, time_seconds)
            multipliers.append(f"{multiplier:.2f}")
        
        print(f"{time_label:<20} {multipliers[0]:<8} {multipliers[1]:<10} {multipliers[2]:<8} {multipliers[3]:<12}")

if __name__ == "__main__":
    # Run the examples
    demonstrate_traffic_patterns()
    
    # Ask before running actual load test
    response = input("\n🤔 Run actual load test against 172.23.0.5? (y/N): ")
    if response.lower() == 'y':
        run_edge_load_test()
    else:
        print("💭 Skipping actual load test. Configuration and patterns demonstrated!") 