# Cloud-Edge Continuum Research Project

## Project Overview
This research project focuses on creating comprehensive datasets that capture CPU usage patterns and microservice migrations in volatile cloud-edge environments. Using MuBench for workload emulation with real-life trace patterns (e.g., Alibaba traces), we simulate realistic scenarios including node failures, throttling, and dynamic user requests with temporal patterns. The primary goal is to collect and analyze CPU utilization across microservices and nodes, track migration events, and understand system behavior under various conditions.

## Repository Structure

- `/infrastructure` - Kubernetes cluster setup and node management
- `/workloads` - Application deployment and MuBench integration
- `/experiments` - Test scenarios and load generation
- `/config` - Configuration files for all components
- `/data` - Raw and processed metrics storage
- `/scripts` - Automation and utility scripts
- `/policies` - Migration and scaling policies

## Prerequisites

- Docker
- Kubernetes CLI (kubectl)
- K3d
- Python 3.8+

## Installation

### Automated Installation

The easiest way to set up the environment is using the clean_install script:

```bash
# Clone the repository
git clone https://github.com/your-username/cloud-edge-continuum-rp.git
cd cloud-edge-continuum-rp

# Run the clean installation script
./scripts/clean_install.sh
```

This script will:
1. Clean any existing environment
2. Set up the infrastructure (K3d Kubernetes cluster)
3. Install and configure MuBench

### Manual Installation

If you prefer to install components separately:

1. Set up infrastructure:
```bash
./infrastructure/setup.sh
```

2. Install MuBench:
```bash
./workloads/setup_mubench.sh
```

## Running Experiments

To run a basic experiment:

```bash
./scripts/run_experiment.sh
```

## Core Components

### 1. Infrastructure Management (`/infrastructure`)
- Kubernetes cluster setup with volatile node configurations
- Node volatility simulation (failures, throttling)
- Resource constraints implementation
- Node health monitoring
- Migration trigger mechanisms

### 2. Workloads (`/workloads`)
- Application deployment configurations
- MuBench integration setup
- Service dependency definitions
- Base workload patterns from traces
- Migration policy implementations
- Resource requirement definitions
- Service mesh configurations
- Application scaling rules

### 3. Experiments (`/experiments`)
- Dynamic user request generators
- Temporal pattern simulators (hourly, daily patterns)
- Burst load generators
- Node failure scenarios
- Throttling experiment definitions
- Migration trigger scenarios
- Multi-workload interaction tests
- Performance measurement setups

## Documentation
For detailed information about MuBench, see the [MuBench Manual](mubench_manual.md).

## Run inside mubench for an example application
python3 Deployers/K8sDeployer/RunK8sDeployer.py -c Configs/K8sParameters.json


## How this project should idealy be used.
User goes in cli: setup-project --> a Workspace enviroment spawns (Folder). We should have folders for Infastracture and Apps, and experiments. The user can interact with the cli to create a template folder for infastracture (basicly one config.) or a template application directory. The application directory will have a workmodel.json describing the app or example Generators inside a generators folder. When the app is deployed a yaml folder will apear with the deployed yamls (i need to decide if the yamls will be persisten after undeploying the app). Also inside the folder there should be a k8parameters.json file. The experiment folder will have a config for the apps that will be used and the infastracture (specified by name). 