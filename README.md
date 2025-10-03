# Cloud-Edge Continuum Research Project

## Project Overview

This research project focuses on creating comprehensive datasets that capture CPU usage patterns and microservice migrations in volatile cloud-edge environments. Using MuBench for workload emulation with configurable service topologies, we simulate realistic scenarios including node failures, throttling, and dynamic user requests. The primary goal is to collect and analyze CPU utilization across microservices and nodes, track migration events, and understand system behavior under various conditions in cloud-edge continuum settings.

## Repository Structure

- `/APPS/` - Pre-configured application examples with `workmodel.json` and `k8parameters.json` files, plus generated Kubernetes YAMLs
- `/infrastructure/` - K3d Kubernetes cluster setup, node management, monitoring stack (Prometheus, Grafana, Kiali)
- `/mu_bench/` - Python package for workload emulation, deployment automation, and experiment management
  - `/mu_bench/mu_bench/` - Core package modules (deployers, generators, metrics, visualization)
  - `pyproject.toml` - Package configuration and dependencies
- `/scripts/` - Jupyter notebooks and Python scripts for experiment execution and visualization
- `/service_cell/` - Microservice container implementation with workload simulation capabilities

## Key Concepts and Architecture

This project emulates geo-distributed microservice applications on a single k3d Kubernetes cluster, with nodes labeled as cloud or edge zones (e.g., `cloud`, `edge-site-1`, `edge-site-2`). The emulation is driven by a `workmodel.json` file that defines service instances, their computational workloads, external service dependencies, and deployment configurations with node affinity for topology-aware placement.

External requests enter through entry services (like `iot-device-gateway`) and create dynamic call graphs by randomly invoking dependent services, mimicking real-world microservice interactions. The system supports workload simulation through configurable CPU and memory stress patterns, enabling realistic performance studies in cloud-edge environments.

## Prerequisites

- Docker
- Kubernetes CLI (kubectl)
- K3d
- Python 3.8+
- jq, yq (installed automatically by setup scripts)

## Installation

### Step 1: Deploy K3d Cluster

First, set up the Kubernetes infrastructure:

```bash
# Clone the repository
git clone https://github.com/your-username/cloud-edge-continuum-rp.git
cd cloud-edge-continuum-rp

# Set up the infrastructure (K3d cluster + monitoring)
./infrastructure/setup.sh
```

This script will:

1. Install required dependencies (K3d, yq, jq)
2. Create a K3d Kubernetes cluster with configurable nodes
3. Apply resource limits and zone labels to nodes
4. Optionally install monitoring stack (Prometheus, Grafana, Kiali)

### Step 2: Set Up Python Virtual Environment and Install MuBench Package

Create a virtual environment and install the MuBench package in development mode:

```bash
# Create virtual environment in the project root
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the mu_bench package in editable mode
pip install -e mu_bench/
```

**Note:** Once the virtual environment is activated, you can import `mu_bench` from any directory on your system. The virtual environment only needs to be activated once per terminal session.

### Step 3: Deploy Applications

Deploy one of the pre-configured applications:

```bash
# Example: Deploy the IoT Gateway application
python3 -c "
import sys
sys.path.append('.')
from mu_bench.deployers.manager import K8sDeploymentManager

manager = K8sDeploymentManager()
manager.deploy_from_workmodel('APPS/app-iot-gateway/workmodel.json')
"

# Or use the deployment notebook
jupyter notebook scripts/deploy_apps.ipynb
```

## Example Applications

The project includes three pre-configured microservice applications:

### 1. IoT Gateway System

- **Services**: IoT Device Gateway, Edge Data Processor, Cloud Analytics Engine
- **Topology**: Edge devices → Edge processing → Cloud analytics
- **Use Case**: Real-time IoT data processing with cloud-based complex analytics

### 2. Smart Manufacturing System

- **Services**: Sensor ingestion, edge preprocessing, anomaly detection, predictive maintenance, production optimization
- **Topology**: Multi-tier edge processing with cloud coordination
- **Use Case**: Industrial IoT with real-time control and predictive analytics

### 3. Smart City Traffic Management

- **Services**: Traffic sensors, edge analytics, signal control, incident detection, central optimization
- **Topology**: Distributed edge processing with centralized coordination
- **Use Case**: Urban traffic management with real-time local control and city-wide optimization

Each application includes:

- `workmodel.json`: Service definitions, workloads, and dependencies
- `k8parameters.json`: Kubernetes deployment parameters
- Generated `yamls/`: Kubernetes manifests for deployment

## Running Experiments

### Quick Start with Example Apps

Use the provided Jupyter notebooks for experiment execution:

```bash
# Deploy applications and run experiments
jupyter notebook scripts/deploy_apps.ipynb

# Run edge experiments with traffic generation
jupyter notebook scripts/experiment.ipynb

# Visualize results
jupyter notebook scripts/visulize.ipynb
```

### Python API Usage

```python
import sys
sys.path.append('.')

from kubernetes import client, config
from mu_bench.deployers.manager import K8sDeploymentManager

# Load Kubernetes config
config.load_kube_config()

# Deploy an application
manager = K8sDeploymentManager()
manager.deploy_from_workmodel('APPS/app-iot-gateway/workmodel.json')

# Run experiment with traffic generation
# (See scripts/experiment.ipynb for complete examples)
```

## Core Components

### 1. Infrastructure Management (`/infrastructure`)

- **K3d Cluster Setup**: Automated cluster creation with configurable node topology
- **Node Management**: Resource limits, zone labeling, and affinity rules
- **Monitoring Stack**: Prometheus, Grafana, and Kiali for metrics collection and visualization
- **Chaos Engineering**: Optional Chaos Mesh integration for fault injection

### 2. MuBench Framework (`/mu_bench`)

Modular Python library with the following components:

#### Generators

- `service_graph_generator.py`: Creates service topologies using random or Barabasi-Albert models
- `work_model_generator.py`: Generates complete workmodel configurations from service graphs

#### Deployers

- `manager.py`: Main deployment orchestration
- `k8s_api/`: Direct Kubernetes API deployment with YAML generation
- `yaml_based/`: Template-based deployment system

#### Request Generation

- `edge_request_generator.py`: Traffic pattern simulation with temporal characteristics
- `edge_profiles.py`: Configurable request profiles for different edge scenarios
- `load_shape.py`: Load pattern definitions (constant, sinusoidal, spike patterns)

#### Metrics & Visualization

- `visualization/`: Comprehensive metrics analysis system
  - CPU/memory utilization analysis
  - Pod-level and node-level metrics
  - Istio service mesh latency analysis
  - Zone correlation analysis
  - Anomaly detection and performance ranking

#### Experiment Management

- `experiment_manager/`: Automated experiment execution with metrics collection
- `metrics_exporter/`: Prometheus metrics export functionality

### 3. Service Cell (`/service_cell`)

Containerized microservice implementation with:

- CPU/memory stress simulation
- Configurable service dependencies
- REST API endpoints
- Workload pattern execution

## Experiment Workflow

1. **Setup Infrastructure**:

   ```bash
   ./infrastructure/setup.sh
   ```

2. **Deploy Application**:

   ```python
   from mu_bench.deployers.manager import K8sDeploymentManager
   manager = K8sDeploymentManager()
   manager.deploy_from_workmodel('APPS/app-iot-gateway/workmodel.json')
   ```

3. **Run Experiment**:
   Use `scripts/experiment.ipynb` for traffic generation and metrics collection

4. **Analyze Results**:

   ```python
   from mu_bench.visualization import MetricsVisualizer
   viz = MetricsVisualizer('DATA/experiment_001/metrics/')
   viz.show_summary()
   viz.plot_all()
   ```

## Visualization and Analysis

The project includes a comprehensive visualization system for analyzing experimental results:

### Available Analysis Types

- **Node-level**: CPU/memory usage, resource correlations, zone analysis
- **Pod-level**: Individual service performance, namespace analysis
- **Network**: Istio latency analysis, service mesh performance
- **Advanced**: Anomaly detection, performance ranking, trend analysis

### Usage Examples

```python
from mu_bench.visualization import MetricsVisualizer

# Basic analysis
viz = MetricsVisualizer('DATA/metrics/')
viz.plot_cpu_analysis()
viz.plot_memory_analysis()

# Advanced analysis
viz.plot_cpu_analysis_advanced()
viz.plot_service_mesh_analysis()

# Summary statistics
viz.show_summary()
```

## Configuration

### Cluster Topology (`infrastructure/nodes.json`)

```json
[
  {"zone": "cloud", "cpu_capacity": 4, "memory_capacity_gb": 8},
  {"zone": "edge-site-1", "cpu_capacity": 2, "memory_capacity_gb": 4},
  {"zone": "edge-site-2", "cpu_capacity": 2, "memory_capacity_gb": 4}
]
```

### Application Definition (`workmodel.json`)

Services with workloads, dependencies, and deployment configurations:

- CPU/memory stress patterns
- Service call probabilities
- Node affinity rules
- Autoscaling policies

## Development and Extension

### Adding New Applications

1. Create directory in `/APPS/`
2. Define `workmodel.json` with services and dependencies
3. Configure `k8parameters.json` for deployment parameters
4. Use deployment scripts to generate and apply Kubernetes manifests

### Custom Workload Patterns

Extend the service cell or create custom generators for specific workload characteristics.

### Metrics Collection

The system supports Prometheus metrics export and custom metric collection for specialized analysis.

## Project Status

✅ **Completed**:

- Modular Python library structure
- K3d-based infrastructure automation
- Three example applications (IoT, Manufacturing, Smart City)
- Comprehensive visualization and analysis system
- Automated experiment execution framework

🔄 **In Progress**:

- Istio integration for advanced routing
- User location-aware traffic patterns
- Enhanced chaos engineering scenarios

📋 **Planned**:

- Additional application templates
- Cloud migration simulation
- Advanced fault injection patterns
- Performance benchmarking suite
