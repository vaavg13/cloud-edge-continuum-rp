# Cloud-Edge Continuum Research Platform

This project provides a platform for conducting research on cloud-edge continuum architectures using K3D and MuBench.

## Project Structure

```
cloud-edge-continuum-rp/
├── config/                      # Configuration files
│   ├── default.yaml             # Main configuration file
│   └── mubench/                 # MuBench configurations
│       ├── K8sParameters.json   # Main MuBench configuration
│       └── ...
├── data/                        # Data collection and processing
│   ├── collectors/              # Data collection modules
│   │   └── log.py               # Metrics collection
│   └── datasets/                # Generated datasets
├── infrastructure/              # Infrastructure management
│   ├── setup.sh                 # Setup script
│   └── docker/                  # Docker image definitions
│       └── k3d.Dockerfile       # Custom K3D image with traffic control
├── policies/                    # Scheduling and migration policies
│   └── affinity/                # Node affinity policies
├── scripts/                     # Utility scripts
│   └── run_experiment.sh        # Experiment runner script
├── src/                         # Source code
│   └── core/                    # Core functionality
│       ├── apply_affinity_polices.py
│       └── drain_nodes.py
├── workloads/                   # Workload definitions
│   └── generators/              # Load generators
│       └── locustfile.py        # Locust load testing
├── logging/                     # Legacy metrics logs
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```



## Ideal project stracture:
cloud-edge-continuum-rp/
├── config/                       # Configuration files
│   ├── default.yaml              # Default configuration
│   ├── profiles/                 # Different experiment profiles
│   │   ├── high_volatility.yaml  # Config for high node volatility 
│   │   └── low_latency.yaml      # Config for low latency scenarios
│   └── mubench/                  # MuBench specific configurations
│       └── K8sParameters.json    # K8s deployment parameters
│
├── infrastructure/               # Infrastructure management
│   ├── setup.sh                  # Main setup script
│   ├── cleanup.sh                # Environment cleanup
│   └── modules/                  # Modular infrastructure components
│       ├── cluster.sh            # Cluster creation/management
│       ├── network.sh            # Network configuration
│       └── nodes.sh              # Node management
│
├── workloads/                    # Workload definitions
│   ├── patterns/                 # Request patterns
│   │   ├── simple_requests.py    # Basic request patterns
│   │   └── complex_patterns.py   # More complex request patterns
│   └── generators/               # Load generators
│       └── locustfiles/          # Locust configurations
│           ├── basic_load.py     # Basic load testing
│           └── realistic_load.py # Realistic usage patterns
│
├── policies/                     # Scheduling and migration policies
│   ├── affinity/                 # Node affinity policies
│   │   └── zone_affinity.yaml    # Zone-based affinity rules
│   ├── migration/                # Migration policies
│   │   └── load_based.py         # Load-based migration
│   └── volatility/               # Node volatility simulation
│       └── edge_volatility.py    # Edge node volatility patterns
│
├── data/                         # Data collection and processing
│   ├── collectors/               # Data collection modules
│   │   ├── metrics.py            # Metrics collection
│   │   ├── events.py             # Event logging
│   │   └── traces.py             # Distributed tracing
│   ├── processors/               # Data processing utilities
│   │   ├── aggregator.py         # Data aggregation
│   │   └── normalizer.py         # Data normalization
│   ├── storage/                  # Data storage configurations
│   │   └── database.py           # Database connections
│   └── datasets/                 # Generated datasets (or symlinks)
│       └── README.md             # Dataset documentation
│
├── src/                          # Core functionality
│   ├── core/                     # Core system components
│   │   ├── controller.py         # Main control logic
│   │   └── scheduler.py          # Workload scheduler
│   ├── models/                   # Data models
│   │   └── metrics.py            # Metrics model
│   └── utils/                    # Utility functions
│       ├── kubernetes.py         # K8s helpers
│       └── logging.py            # Logging utilities
│
├── experiments/                  # Experiment definitions
│   ├── scenarios/                # Predefined scenarios
│   │   ├── baseline.py           # Baseline experiment
│   │   └── high_load.py          # High load experiment
│   └── run.py                    # Experiment runner
│
├── scripts/                      # Utility scripts
│   ├── run_experiment.sh         # Experiment runner script
│   └── visualize_results.py      # Results visualization
│
├── tests/                        # Tests
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
│
├── docs/                         # Documentation
│   ├── architecture.md           # System architecture
│   └── experiments.md            # Experiment documentation
│
├── requirements.txt              # Python dependencies
├── setup.py                      # Package installation
└── README.md                     # Main project documentation

## Getting Started

1. Clone the repository
2. Set up the environment
   ```bash
   ./infrastructure/setup.sh
   ```
   This will install all dependencies, create the K3D cluster, label nodes, and install MuBench after asking for confirmation.
   
3. Run an experiment
   ```bash
   ./scripts/run_experiment.sh
   ```
   This will run the complete experiment after asking for confirmation.

## Configuration

The main configuration is in `config/default.yaml`. MuBench-specific configurations are stored in the `config/mubench/` directory, with `K8sParameters.json` being the main configuration file.

## Scripts

- `infrastructure/setup.sh`: Sets up the environment, creates the K3D cluster, configures nodes, and installs MuBench
  - Usage: `./infrastructure/setup.sh` (with confirmation prompt)
- `scripts/run_experiment.sh`: Runs experiments and collects metrics
  - Usage: `./scripts/run_experiment.sh` (complete experiment with confirmation)
  - Usage: `./scripts/run_experiment.sh run-test` (run just the load test)
  - Usage: `./scripts/run_experiment.sh cleanup` (clean up resources)


## TO DO
Dynamic CPU Stress Patterns:
  While MuBench supports CPU stress, we need to implement dynamic patterns:
  Add time-based CPU stress variation
  Implement burst patterns
Node Failure Simulation:
  Current implementation in drain_nodes.py is random
  Need to correlate node failures with CPU stress levels
  Implement gradual CPU degradation patterns
Service Migration Triggers:
  Add CPU-based migration decision logic
  Implement service priority based on CPU requirements
  Add CPU threshold monitoring for migration decisions
Workload Distribution:
  Implement smarter distribution of CPU-intensive services
  Add CPU load balancing between nodes
  Consider CPU capacity when distributing services
Metrics Collection Enhancement:
  Add more granular CPU metrics
  Implement CPU throttling detection
  Add CPU contention metrics

## Requirements

- Docker
- Python 3.8+
- kubectl
- yq (YAML processor)
- Locust (for load testing)

## License

[MIT License](LICENSE)



