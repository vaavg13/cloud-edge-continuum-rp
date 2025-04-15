# Function to run load test
run_load_test() {
    print_status "Running load test..."
    
    # Start metrics logging in background
    python3 -m src.monitoring.log &
    LOG_PID=$!
    
    # Run load test
    locust -f locustfile.py \
        --host $(get_config 'test.host') \
        --users $(get_config 'test.users') \
        --spawn-rate $(get_config 'test.spawn_rate') \
        --run-time $(get_config 'test.duration')
    
    # Kill metrics logging process
    kill $LOG_PID
    
    print_status "Load test completed"
}