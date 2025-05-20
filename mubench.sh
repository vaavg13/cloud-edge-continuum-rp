#!/bin/bash

# Unified CLI dispatcher
case "$1" in
  deploy)
    shift
    python -m mu_bench.cli.deploy_app "$@"
    ;;
  undeploy)
    shift
    python -m mu_bench.cli.undeploy_app "$@"
    ;;
  scaffold)
    shift
    python -m mu_bench.cli.scaffold_app "$@"
    ;;
  export-metrics)
    shift
    python -m mu_bench.cli.export_metrics "$@"
    ;;
  run-experiment)
    shift
    # Ensure that the cecemulator conda environment is activated if necessary
    # For example: conda activate cecemulator
    python -m mu_bench.cli.run_experiment "$@"
    ;;
  scaffold-experiment)
    shift
    # Ensure that the cecemulator conda environment is activated if necessary
    python mu_bench/cli/scaffold_experiment.py "$@"
    ;;
  *)
    echo "Usage: $0 {deploy|undeploy|scaffold|export-metrics|run-experiment|scaffold-experiment} [args...]"
    exit 1
    ;;
esac