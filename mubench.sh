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
  *)
    echo "Usage: $0 {deploy|undeploy|scaffold} [args...]"
    exit 1
    ;;
esac