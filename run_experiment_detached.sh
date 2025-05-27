#!/bin/bash

# Edge Experiment Runner Script
# This script runs the edge experiment in a detached screen session

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="edge_experiment_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$SCRIPT_DIR/experiment_runner.log"

echo "🚀 Starting Edge Experiment in detached mode"
echo "📁 Working directory: $SCRIPT_DIR"
echo "📝 Session name: $SESSION_NAME"
echo "📋 Log file: $LOG_FILE"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda is not available"
    exit 1
fi

# Check if screen is available
if ! command -v screen &> /dev/null; then
    echo "❌ Error: screen is not available"
    exit 1
fi

# Create screen session and run experiment
screen -dmS "$SESSION_NAME" bash -c "
    echo '🌐 Starting Edge Experiment at $(date)' | tee -a '$LOG_FILE'
    echo '📁 Working in: $(pwd)' | tee -a '$LOG_FILE'
    
    # Activate conda environment
    echo '🔧 Activating cecemulator environment...' | tee -a '$LOG_FILE'
    source \$(conda info --base)/etc/profile.d/conda.sh
    conda activate cecemulator
    
    if [ \$? -ne 0 ]; then
        echo '❌ Failed to activate cecemulator environment' | tee -a '$LOG_FILE'
        exit 1
    fi
    
    echo '✅ Environment activated' | tee -a '$LOG_FILE'
    echo '🎯 Starting experiment...' | tee -a '$LOG_FILE'
    
    # Change to script directory
    cd '$SCRIPT_DIR'
    
    # Run the experiment
    python -m mu_bench.test_scripts.run_edge_experiment 2>&1 | tee -a '$LOG_FILE'
    
    echo '🏁 Experiment completed at $(date)' | tee -a '$LOG_FILE'
    echo '💤 Screen session will remain active. Use: screen -r $SESSION_NAME to reconnect'
    
    # Keep session alive for a while to allow reconnection
    echo '⏳ Keeping session alive for 30 minutes...'
    sleep 1800
"

if [ $? -eq 0 ]; then
    echo "✅ Experiment started successfully in screen session: $SESSION_NAME"
    echo ""
    echo "📋 Useful commands:"
    echo "   • View running sessions: screen -ls"
    echo "   • Reconnect to session:  screen -r $SESSION_NAME"
    echo "   • View live log:         tail -f $LOG_FILE"
    echo "   • Kill session:          screen -S $SESSION_NAME -X quit"
    echo ""
    echo "🔍 You can now safely close this connection."
else
    echo "❌ Failed to start experiment"
    exit 1
fi 