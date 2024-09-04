import requests
import csv
import time
import os

STEP = '30s'
FOLDER = './logging'

# Prometheus server URL
PROMETHEUS = "http://192.168.192.2:30000"

# Function to query Prometheus for a time range
def query_prometheus_range(query, start_time, end_time):
    response = requests.get(f"{PROMETHEUS}/api/v1/query_range", params={
        'query': query,
        'start': start_time,
        'end': end_time,
        'step': '30s'
    })
    result = response.json()
    return result['data']['result']

# Function to get node metadata (name and zone) from Prometheus
def get_node_metadata():
    query = 'targets'  # Adjusting the query to fetch node info
    response = requests.get(f"{PROMETHEUS}/api/v1/query", params={'query': query})
    result = response.json()['data']['result']
    # Create a mapping of instance IP to node name and zone
    
    metadata = {}
    for item in result:
        instance_ip = item['metric']['internal_ip']
        node_name = item['metric']['node']
        metadata[instance_ip] = {
            'node_name': node_name
        }

    return metadata

def get_pod_node_mapping():
    query = 'kube_pod_info'
    response = requests.get(f"{PROMETHEUS}/api/v1/query", params={'query': query})
    result = response.json()['data']['result']

    pod_node_mapping = {}
    for item in result:
        pod_name = item['metric']['pod']
        node_name = item['metric']['node']
        pod_node_mapping[pod_name] = node_name

    return pod_node_mapping



# Function to append data to CSV with folder creation and column labels
def append_to_csv(folder, filename, data, metadata, pod_mapping=None):
    # Ensure the directory exists
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Full path to the file
    filepath = os.path.join(folder, filename)
    
    # Check if the file exists to decide if headers are needed
    file_exists = os.path.isfile(filepath)

    # Append data to the CSV file
    with open(filepath, mode='a', newline='') as file:
        writer = csv.writer(file)
        
        # Write column headers if the file is new
        if not file_exists:
            if pod_mapping:
                writer.writerow(['timestamp', 'node_name', 'pod_name', 'metric_value'])
            else:
                writer.writerow(['timestamp', 'node_name', 'metric_value'])
        
        for entry in data:
            metric = entry['metric']
            instance_ip = metric.get('instance', '').split(':')[0]
            node_name = metadata.get(instance_ip, {}).get('node_name', instance_ip)
            for value in entry['values']:
                timestamp = value[0]
                metric_value = value[1]
                if pod_mapping:
                    pod_name = metric.get('pod', 'unknown')
                    mapped_node_name = pod_mapping.get(pod_name, 'unknown')
                    writer.writerow([timestamp, mapped_node_name, pod_name, metric_value])
                else:
                    writer.writerow([timestamp, node_name, metric_value])

# Queries
node_cpu_query = 'sum(rate(node_cpu_seconds_total{mode!="idle"}[1m])) by (instance)'
node_memory_query = 'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100'
pod_cpu_query = 'sum(rate(container_cpu_usage_seconds_total[1m])) by (pod, namespace)'
pod_memory_query = 'sum(container_memory_usage_bytes) by (pod, namespace)'


# Real-time logging loop
def real_time_logging(duration, interval=300):
    start_time = time.time()
    folder = 'metrics_logs'  # Specify the folder where the CSV files will be saved

    # Retrieve node metadata (name and zone)
    node_metadata = get_node_metadata()
    pod_node_mapping = get_pod_node_mapping()

    while True:
        end_time = time.time()

        print("Querying Prometheus and logging metrics...")
        
        # Query Prometheus for the last interval
        node_cpu_data = query_prometheus_range(node_cpu_query, start_time, end_time)
        node_memory_data = query_prometheus_range(node_memory_query, start_time, end_time)
        pod_cpu_data = query_prometheus_range(pod_cpu_query, start_time, end_time)
        pod_memory_data = query_prometheus_range(pod_memory_query, start_time, end_time)

        # Append to CSV in the specified folder
        append_to_csv(folder, 'node_cpu_usage.csv', node_cpu_data, node_metadata)
        append_to_csv(folder, 'node_memory_usage.csv', node_memory_data, node_metadata)
        append_to_csv(folder, 'pod_cpu_usage.csv', pod_cpu_data, node_metadata, pod_node_mapping)
        append_to_csv(folder, 'pod_memory_usage.csv', pod_memory_data, node_metadata, pod_node_mapping)
        # Update start_time for next interval
        start_time = end_time

        # Calculate remaining time to sleep, ensuring it's not negative
        elapsed_time = time.time() - start_time
        sleep_time = interval - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)

        # Check if the total duration has been exceeded
        if end_time - start_time > duration:
            break

# Start the real-time logging
# Set the total duration for logging (e.g., duration of Locust test) and interval
test_duration = 3600  # Total test duration in seconds (e.g., 1 hour)
log_interval = 30  # Interval for logging in seconds (e.g., log every 5 minutes)

real_time_logging(test_duration, log_interval)

print("Logging completed.")

print(get_node_metadata())