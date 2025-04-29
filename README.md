# Cloud-Edge Continuum Research Project

## Project Overview

This research project focuses on creating comprehensive datasets that capture CPU usage patterns and microservice migrations in volatile cloud-edge environments. Using MuBench for workload emulation with real-life trace patterns (e.g., Alibaba traces), we simulate realistic scenarios including node failures, throttling, and dynamic user requests with temporal patterns. The primary goal is to collect and analyze CPU utilization across microservices and nodes, track migration events, and understand system behavior under various conditions.

## Repository Structure

- `/APPS/` - This is where generated or active applications are stored, each with `generators/` and `yamls/` subfolders. Each app is described by `workmodel.json` and `k8parameters.json`.
- `/infrastructure/` - Kubernetes cluster setup, node management, add-ons, and monitoring (e.g., dashboards, manifests).
- `/mu_bench/` - Main MuBench workload emulation framework, including CLI, deployers, generators, request generators, service cell logic, templates, test scripts, and utilities.
- `/scripts/` - Various utility or alternative execution scripts.

## Key Concepts and Architecture

This project emulates geo-distributed microservice (MS) applications on a single k3d Kubernetes cluster, with nodes labeled as either cloud or edge zones (e.g., cloud, edge-site-1, edge-site-2). The emulation is driven by a `workmodel.json` file, which defines each MS instance (such as s0, s1, etc.) and their deployment configuration, including node affinity to control placement on specific zones. All external requests enter through s0, which then randomly calls other services, forming a dynamic call graph that mimics real-world MS interactions.

The project is being refactored for modularity and automation, with a focus on using a standardized Python library structure and minimizing manual command sequences. Node affinity and topology-aware deployment are being integrated directly into the deployment logic, and Istio is planned for ingress and advanced routing. The goal is to enable realistic experimentation with cloud-edge placement, user location-aware routing, and system behavior under various scenarios, all while keeping the internal MS logic unchanged for now.

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
    # (see mu_bench/ for details)
    ```

## Running Experiments

To run a basic experiment:

```bash
./scripts/run_experiment.sh
```

## Core Components

### 1. Infrastructure Management (`/infrastructure`)

- K3d Kubernetes cluster setup 
- Node volatility simulation (failures, throttling)
- Resource constraints implementation
- Monitoring Instalation

### 2. Application Management (`/APPS`)

- Application templates and deployment configurations
- `workmodel.json` for describing microservice structure and placement
- Service dependency definitions and resource requirements
- Generated deployment yamls

### 3. MuBench Framework (`/mu_bench`)

- Workload emulation, request generation, and deployment automation
- CLI tools, deployers, and experiment templates
- **Note:** `/mu_bench/add_ons/` is deprecated and will be refactored in future releases

## Application Lifecycle (CLI Usage)

### 1. Scaffold a New Application

To create a new application directory from the template (in `APPS/` by default):

```bash
python3 -m mu_bench.cli.scaffold_app create -n <app_name>
```

- Use `--apps-dir <dir>` to specify a different parent directory.
- Use `-e <example_workmodel.json>` to copy an example workmodel into your new app.

To list available example workmodels:

```bash
python3 -m mu_bench.cli.scaffold_app list
```

### 2. Deploy an Application

To deploy an app (must contain a valid `workmodel.json`):

```bash
python3 -m mu_bench.cli.deploy_app --app-dir APPS/<app_name>
```

This will generate Kubernetes YAMLs in `APPS/<app_name>/yamls/` and apply them to your cluster.

### 3. Undeploy an Application

To undeploy an app and remove its resources from the cluster:

```bash
python3 -m mu_bench.cli.undeploy_app --app-dir APPS/<app_name>
```

---

## Generators

- `mu_bench/generators/service_graph_generator.py`: Generates service graphs (topologies) for microservice applications, supporting random and Barabasi models, with optional database nodes.
- `mu_bench/generators/work_model_generator.py`: Generates work models (service definitions, resource configs, etc.) from a service graph and parameter set.

These are used to automate the creation of realistic microservice topologies and configurations, which are then placed in your app's `generators/` or used to produce `workmodel.json`.

---

## Deployers

- The deployment logic is managed by `mu_bench/deployers/manager.py` and related files.
- The CLI (`deploy_app.py`, `undeploy_app.py`) wraps this logic for user-friendly operation.
- YAMLs are generated and applied automatically; advanced users can customize templates or parameters in `k8parameters.json`.

---

## Example Workflow

```bash
# 1. Scaffold a new app
python3 -m mu_bench.cli.scaffold_app create -n myapp

# 2. (Optional) Generate a service graph and workmodel using the generators
#    (see mu_bench/generators/ for scripts and usage)

# 3. Deploy the app
python3 -m mu_bench.cli.deploy_app --app-dir APPS/myapp

# 4. Undeploy the app
python3 -m mu_bench.cli.undeploy_app --app-dir APPS/myapp
```

---

## Project Roadmap & Next Steps

- Refactor for modular Python library structure and improved automation
- Integrate node affinity and topology-aware deployment directly into deployment logic
- Add Istio for ingress and advanced routing
- Enable user location-aware routing and realistic cloud-edge placement experiments
- Refactor or remove deprecated components (notably `mu_bench/add_ons/`)
- Expand documentation and add more example applications and experiment templates