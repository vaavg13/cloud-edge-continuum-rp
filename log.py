import requests
import csv
import time
import os

# Global Variables for Filenames
NODE_CPU_FILE = 'node_cpu_usage.csv'
NODE_MEMORY_FILE = 'node_memory_usage.csv'
POD_CPU_FILE = 'pod_cpu_usage.csv'
POD_MEMORY_FILE = 'pod_memory_usage.csv'

# Configurations
STEP = '30s'
FOLDER = './logging'
DURATION = 3600  # 1 hour
LOG_INTERVAL = 30  # Interval between log entries
RUN_INDEF = True

# Prometheus server URL
PROMETHEUS = "http://192.168.192.2:30000"

# Queries
node_cpu_query = 'sum(rate(node_cpu_seconds_total{mode!="idle"}[1m])) by (instance)'
node_memory_query = 'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100'
pod_cpu_query = 'sum(rate(container_cpu_usage_seconds_total[1m])) by (pod, namespace)'
pod_memory_query = 'sum(container_memory_usage_bytes) by (pod, namespace)'


def setup_experiment_directory(parent_folder):
    """ Set up the directory for the experiment and create the necessary files with headers. """
    timestr = time.strftime("%Y%m%d-%H%M%S")
    experiment_folder = 'experiment_' + timestr
    folder = os.path.join(parent_folder, experiment_folder)
    
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Create the files with headers
    filepaths = {
        'node_cpu': os.path.join(folder, NODE_CPU_FILE),
        'node_memory': os.path.join(folder, NODE_MEMORY_FILE),
        'pod_cpu': os.path.join(folder, POD_CPU_FILE),
        'pod_memory': os.path.join(folder, POD_MEMORY_FILE)
    }

    for key, filepath in filepaths.items():
        if not os.path.isfile(filepath):
            with open(filepath, mode='w', newline='') as file:
                writer = csv.writer(file)
                if 'pod' in key:
                    writer.writerow(['timestamp', 'node_name', 'pod_name', 'metric_value'])
                else:
                    writer.writerow(['timestamp', 'node_name', 'metric_value'])

    return filepaths

def append_to_csv(filepath, data, metadata, pod_mapping=None):
    """ Append data to the CSV file. """
    with open(filepath, mode='a', newline='') as file:
        writer = csv.writer(file)
        
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

def query_prometheus_range(query, start_time, end_time):
    response = requests.get(f"{PROMETHEUS}/api/v1/query_range", params={
        'query': query,
        'start': start_time,
        'end': end_time,
        'step': STEP
    })
    result = response.json()
    return result['data']['result']

def get_node_metadata():
    query = 'targets'
    response = requests.get(f"{PROMETHEUS}/api/v1/query", params={'query': query})
    result = response.json()['data']['result']
    
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

# Real-time logging loop
def real_time_logging(duration, interval=300, run_until_terminated=False):
    start_time = time.time()
    folder = FOLDER

    # Setup the directory and files for logging
    filepaths = setup_experiment_directory(folder)

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
        append_to_csv(filepaths['node_cpu'], node_cpu_data, node_metadata)
        append_to_csv(filepaths['node_memory'], node_memory_data, node_metadata)
        append_to_csv(filepaths['pod_cpu'], pod_cpu_data, node_metadata, pod_node_mapping)
        append_to_csv(filepaths['pod_memory'], pod_memory_data, node_metadata, pod_node_mapping)

        # Update start_time for next interval
        start_time = end_time

        # Calculate remaining time to sleep, ensuring it's not negative
        elapsed_time = time.time() - start_time
        sleep_time = interval - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)

        # Check if the total duration has been exceeded unless running indefinitely
        if not run_until_terminated and (end_time - start_time > duration):
            break


if __name__ == "__main__":
    # Run indefinitely by passing True to the run_until_terminated argument
    real_time_logging(DURATION, LOG_INTERVAL, run_until_terminated=RUN_INDEF)

    print("Logging completed.")