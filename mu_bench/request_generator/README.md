# EdgeRequestGenerator - Simplified Edge Computing Load Testing

A dramatically simplified solution for generating realistic load patterns specifically designed for **edge computing scenarios**. Perfect for cloud-edge continuum research!

## 🚀 Key Features

- **Edge-Centric Design**: Focuses on edge sites rather than generic applications
- **Realistic Edge Patterns**: Urban, suburban, rural, industrial traffic characteristics
- **Port-Based Apps**: Differentiates applications by port (matches real edge infrastructure)
- **Automatic Endpoint Generation**: Creates `s0-{edge-site}` patterns automatically
- **Zero Configuration Files**: Everything defined in simple Python dictionaries
- **Minimal Complexity**: 70% less configuration than traditional load generators

## 📦 Project Structure

```files
mu_bench/request_generator/
├── __init__.py                     # Module exports
├── edge_request_generator.py       # Main EdgeRequestGenerator class
├── edge_calculator.py              # Simple edge traffic calculator
├── edge_profiles.py                # Built-in edge site patterns
├── edge_example.py                 # Practical usage examples
├── load_shape.py                   # Load shape management
└── README.md                       # This file
```

## 🎯 Quick Start

### Basic Edge Load Test

```python
from mu_bench.request_generator import EdgeRequestGenerator

# Simple edge configuration
config = {
    "base_host": "172.23.0.5",
    "apps": [
        {"name": "app-1", "port": 31116, "traffic_weight": 1.0},
        {"name": "app-2", "port": 31115, "traffic_weight": 0.8}
    ],
    "edge_sites": {
        "edge-site-1": {"pattern": "urban_peak", "traffic_weight": 1.0},
        "edge-site-2": {"pattern": "suburban_steady", "traffic_weight": 0.7},
        "edge-site-3": {"pattern": "rural_minimal", "traffic_weight": 0.3}
    }
}

# Run load test
generator = EdgeRequestGenerator()
success = generator.run_edge_experiment(
    edge_config=config,
    max_users=20,
    spawn_rate=5,
    run_duration_seconds=300
)
```

### Generated Endpoints

The above configuration automatically generates requests to:
- `http://172.23.0.5:31116/s0-edge-site-1`
- `http://172.23.0.5:31116/s0-edge-site-2` 
- `http://172.23.0.5:31116/s0-edge-site-3`
- `http://172.23.0.5:31115/s0-edge-site-1`
- `http://172.23.0.5:31115/s0-edge-site-2`
- `http://172.23.0.5:31115/s0-edge-site-3`

## 🏙️ Built-in Edge Site Patterns

### Available Patterns

- **`urban_peak`**: High-density urban areas with business hour peaks
- **`suburban_steady`**: Moderate, steady suburban traffic
- **`rural_minimal`**: Low, consistent rural traffic  
- **`industrial_shift`**: Shift-based factory patterns (6am, 2pm, 10pm peaks)
- **`residential_evening`**: Evening and weekend peaks (6-9pm)
- **`commercial_business`**: Strict business hours (9am-5pm)

### Traffic Characteristics

Each pattern includes:
- **Peak Hours**: When traffic is highest
- **Peak Multiplier**: How much traffic increases during peaks
- **Off-Peak/Night Multipliers**: Traffic levels during other times
- **Burst Probability**: Chance of random traffic spikes
- **Base Traffic Weight**: Overall traffic level for this site type

## 🔧 Configuration Format

### Minimal Configuration

```python
{
    "base_host": "172.23.0.5",
    "apps": [
        {"name": "main-app", "port": 31116, "traffic_weight": 1.0}
    ],
    "edge_sites": {
        "edge-site-1": {"pattern": "urban_peak", "traffic_weight": 1.0}
    }
}
```

### Full Configuration Options

```python
{
    "base_host": "172.23.0.5",                    # Target host
    "apps": [
        {
            "name": "app-1",                       # App identifier
            "port": 31116,                         # Port number
            "traffic_weight": 1.0,                 # Relative traffic weight
            "wait_time": {"min": 0.5, "max": 2.0} # Optional: request intervals
        }
    ],
    "edge_sites": {
        "edge-site-1": {
            "pattern": "urban_peak",               # Traffic pattern type
            "description": "Downtown site",       # Optional description
            "traffic_weight": 1.0                 # Relative site traffic
        }
    }
}
```

## 📊 Real-time Statistics

```python
generator = EdgeRequestGenerator()
generator.run_edge_experiment(config, max_users=20)

# Get statistics during or after experiment
stats = generator.get_stats()
print(f"""
📊 Edge Load Test Results:
   Total Requests: {stats['total_requests']}
   Requests/Second: {stats['requests_per_second']:.2f}
   Average Response Time: {stats['average_response_time']:.2f}ms
   Failure Rate: {stats['failure_rate']:.2%}
""")
```

## 🧪 Integration with Experiments

Perfect for edge computing research:

```python
class EdgeExperiment:
    def __init__(self, name: str):
        self.name = name
        self.generator = EdgeRequestGenerator()
    
    def run_migration_test(self, edge_config: dict) -> dict:
        """Test microservice migration between edge sites."""
        success = self.generator.run_edge_experiment(
            edge_config=edge_config,
            max_users=30,
            run_duration_seconds=600
        )
        return self.generator.get_stats()
```

## 🕐 Traffic Pattern Examples

Different edge sites have realistic traffic patterns:

| Time | Urban | Suburban | Rural | Industrial |
|------|-------|----------|-------|------------|
| 6 AM | 0.15  | 0.30     | 0.42  | 1.60       |
| 9 AM | 2.50  | 1.44     | 0.42  | 0.32       |
| 3 PM | 2.50  | 0.90     | 0.42  | 1.60       |
| 6 PM | 0.75  | 1.26     | 0.84  | 0.32       |
| 10 PM| 0.10  | 0.15     | 0.42  | 1.20       |

## 🎯 Why Simplified?

### Before (Complex)
```python
# 20+ lines of nested configuration
{
    "name": "web-app",
    "user_weight": 3,
    "port": 8080,
    "targets": [
        {
            "path": "/api/users",
            "site_base_scale": 1.0,
            "site_random_factor_range": [0.8, 1.2],
            "pattern_config_refs": {
                "seasonality_refs": ["office_hours_peak"],
                "burst_refs": ["minor_frequent_glitches"]
            }
        }
    ]
}
```

### After (Simple)
```python
# 3 lines per edge site
{
    "base_host": "172.23.0.5",
    "apps": [{"name": "app-1", "port": 31116, "traffic_weight": 1.0}],
    "edge_sites": {"edge-site-1": {"pattern": "urban_peak", "traffic_weight": 1.0}}
}
```

## 🚀 Benefits for Edge Computing Research

- **Realistic Edge Scenarios**: Models actual edge deployment patterns
- **Geographic Focus**: Urban/suburban/rural site characteristics
- **Infrastructure Matching**: Port-based app differentiation
- **Systematic URLs**: Automatic `s0-{edge-site}` generation
- **Research-Ready**: Perfect for cloud-edge continuum studies
- **Minimal Configuration**: Focus on research, not configuration complexity

## 📚 Examples

See `edge_example.py` for comprehensive examples including:

1. **Basic Edge Test**: Simple load test with multiple sites
2. **Traffic Pattern Demo**: How different sites behave over time
3. **Real Infrastructure**: Using actual IP addresses and ports
4. **Statistics Collection**: Getting detailed performance metrics

## 🔍 API Reference

### EdgeRequestGenerator

#### Constructor
```python
EdgeRequestGenerator(logger: Optional[logging.Logger] = None)
```

#### Main Method
```python
run_edge_experiment(
    edge_config: Dict[str, Any],
    max_users: int = 20,
    spawn_rate: int = 5,
    run_duration_seconds: float = 300,
    simulated_period_seconds: float = 86400,
    log_level: str = "INFO"
) -> bool
```

#### Utility Methods
- `get_stats()`: Get real-time statistics
- `get_edge_patterns()`: List available edge patterns
- `list_available_patterns()`: Show pattern descriptions

---

**Ready for realistic edge computing load testing with minimal configuration!** 🌐 