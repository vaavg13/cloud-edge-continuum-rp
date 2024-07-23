#!/bin/bash

K3D_INSTALL_SCRIPT="https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh"
K3D_IMAGE="ktogias/k3s:v1.30.2-k3s2-tc"
CLUSTER_NAME="continuum"
LOADBALANCER_PORT_MAP=8081
CLOUD_NODES_NUM=2
EDGE_NODES_NUM=4
CLOUD_NODES_CPU_CAPACITY="4"
EDGE_NODES_CPU_CAPACITY="2"
CLOUD_NODES_MEMORY_CAPACITY_GB="4"
EDGE_NODES_MEMORY_CAPACITY_GB="2"

CLOUD_NODES_LABELS=(
    "zone=cloud"
)
EDGE_NODES_LABELS=(
    "zone=edge"
)

EDGE_NODES_NETWORK_RESTRICTIONS=(
    "rate=1mbps"
    "delay=100ms"
    "loss=50%"
    "duplicate=50%"
    "corrupt=10%"
)

MUBENCH_IMAGE="msvcbench/mubench"

TOTAL_NODES=$((CLOUD_NODES_NUM + EDGE_NODES_NUM))
K3D_CLUSTER_CREATE_ARGS=(
    "-p" "${LOADBALANCER_PORT_MAP}:80@loadbalancer"
    "-a" "${TOTAL_NODES}"
    "--image" "${K3D_IMAGE}"
)

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

CLOUD_NODES_MEMORY_CAPACITY_KB=$((CLOUD_NODES_MEMORY_CAPACITY_GB * 1024 * 1024))
EDGE_NODES_MEMORY_CAPACITY_KB=$((EDGE_NODES_MEMORY_CAPACITY_GB * 1024 * 1024))

# Fetch the total available CPU cores and memory of the host machine
TOTAL_CPU=$(lscpu | grep "^CPU(s):" | awk '{print $2}')
TOTAL_MEMORY_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)

# Calculate system reserved CPU and memory for cloud and edge nodes
CLOUD_SYSTEM_RESERVED_CPU=$(( TOTAL_CPU - CLOUD_NODES_CPU_CAPACITY ))
EDGE_SYSTEM_RESERVED_CPU=$(( TOTAL_CPU - EDGE_NODES_CPU_CAPACITY ))

CLOUD_SYSTEM_RESERVED_MEMORY_KB=$(( TOTAL_MEMORY_KB - CLOUD_NODES_MEMORY_CAPACITY_KB ))
EDGE_SYSTEM_RESERVED_MEMORY_KB=$(( TOTAL_MEMORY_KB - EDGE_NODES_MEMORY_CAPACITY_KB ))

NO_RESOURCE_RESTRICTIONS=false
NO_NETWORK_RESTRICTIONS=false
NO_MUBENCH=false

usage_error() {
    echo "Usage: $0 init|up|down|info [--no-resource-restrictions] [--no-network-restrictions] [--no-mubench]"
    echo "Commands:"
    echo "  init                  Install k3d and other dependencies."
    echo "  up                    Start the cluster."
    echo "  down                  Stop the cluster and remove related containers."
    echo "  info                  Get cluster agent nodes info."
    echo "Options for 'up' command:"
    echo "  --no-resource-restrictions     Skip the application of CPU and memory restrictions."
    echo "  --no-network-restrictions      Skip the application of network restrictions."
    echo "  --no-mubench                   Skip the deployment of MuBench."
    exit 1
}

init(){
    #Install k3d
    wget -q -O - "${K3D_INSTALL_SCRIPT}" | bash

    #Pull k3d image
    docker pull ${K3D_IMAGE}
    
    #Pull mubench image
    docker pull ${MUBENCH_IMAGE}

    # Load sch_netem module
    sudo modprobe sch_netem
}

apply_network_restrictions() {
    local agent_name=$1
    local interface_name=$2

    # Extract the values for network restrictions
    rate_value=""
    delay_value=""
    loss_value=""
    duplicate_value=""
    corrupt_value=""

    for restriction in "${EDGE_NODES_NETWORK_RESTRICTIONS[@]}"; do
        case $restriction in
            rate=*) rate_value="${restriction#*=}" ;;
            delay=*) delay_value="${restriction#*=}" ;;
            loss=*) loss_value="${restriction#*=}" ;;
            duplicate=*) duplicate_value="${restriction#*=}" ;;
            corrupt=*) corrupt_value="${restriction#*=}" ;;
        esac
    done

    # Build tc commands dynamically
    tc_commands="tc qdisc add dev ${interface_name} root handle 1: htb default 30 r2q 5;"
    tc_commands+="tc class add dev ${interface_name} parent 1: classid 1:1 htb rate 1000mbit quantum 1514;"

    if [ -n "$rate_value" ]; then
        tc_commands+="tc class add dev ${interface_name} parent 1:1 classid 1:30 htb rate ${rate_value} quantum 1500;"
    fi

    netem_command="tc qdisc add dev ${interface_name} parent 1:30 handle 30: netem"
    [ -n "$delay_value" ] && netem_command+=" delay ${delay_value}"
    [ -n "$loss_value" ] && netem_command+=" loss ${loss_value}"
    [ -n "$duplicate_value" ] && netem_command+=" duplicate ${duplicate_value}"
    [ -n "$corrupt_value" ] && netem_command+=" corrupt ${corrupt_value}"
    netem_command+=";"

    tc_commands+="${netem_command}"

    docker exec "${agent_name}" sh -c "
        iptables -t mangle -A POSTROUTING -o ${interface_name} -j MARK --set-mark 1;
        ${tc_commands}
        tc filter add dev ${interface_name} protocol ip parent 1:0 prio 1 handle 1 fw flowid 1:30;
    "
}

wait_for_pods_ready() {
    echo "Waiting for all pods to be in Running or Completed state..."
    sleep 30
    while true; do
        not_ready_pods=$(kubectl get pods --all-namespaces --field-selector=status.phase!=Running,status.phase!=Succeeded | grep -c -v "NAME")
        if [ "$not_ready_pods" -eq 0 ]; then
            echo "All pods are in Running or Completed state."
            break
        else
            echo "Waiting for $not_ready_pods pods to be ready..."
            sleep 10
        fi
    done
}

start_mubench(){
    docker run -d \
        --rm \
        --name mubench \
        -v ~/.kube/:/root/.kube \
        -v "${SCRIPT_DIR}/mubench/Configs/:/root/muBench/Configs" \
        --network host \
        ${MUBENCH_IMAGE}
}

stop_mubench(){
    docker stop mubench
}

deploy_mubench(){
    docker exec -it mubench bash -c "cd \$HOME/muBench && python3 Deployers/K8sDeployer/RunK8sDeployer.py -c Configs/K8sParameters.json"
}

apply_resource_limits(){
    # Set resource limits for cloud nodes containers
    for ((i=0; i<CLOUD_NODES_NUM; i++)); do
        agent_name="k3d-${CLUSTER_NAME}-agent-${i}"
        if [ "$NO_RESOURCE_RESTRICTIONS" = false ]; then
            docker update --cpus="${CLOUD_NODES_CPU_CAPACITY}" --memory="${CLOUD_NODES_MEMORY_CAPACITY_GB}g" --memory-swap="${CLOUD_NODES_MEMORY_CAPACITY_GB}g" "${agent_name}"
        fi
    done

    # Set resource limits for edge nodes containers
    for ((i=0; i<EDGE_NODES_NUM; i++)); do
        agent_index=$((CLOUD_NODES_NUM + i))
        agent_name="k3d-${CLUSTER_NAME}-agent-${agent_index}"
        if [ "$NO_RESOURCE_RESTRICTIONS" = false ]; then
            docker update --cpus="${EDGE_NODES_CPU_CAPACITY}" --memory="${EDGE_NODES_MEMORY_CAPACITY_GB}g" --memory-swap="${EDGE_NODES_MEMORY_CAPACITY_GB}g" "${agent_name}"
        fi
        # Emulate low network restrictions for edge nodes
        apply_network_restrictions "${agent_name}" "eth0"
    done
}

up(){

    # Check if sch_netem is loaded, if not, load it
    if ! lsmod | grep -q "sch_netem"; then
        echo "Loading sch_netem module. Please provide sudo password if asked..."
        sudo modprobe sch_netem
    fi

    cloud_labels=()
    edge_labels=()
    k3s_args=()

    # Generate k3s-arg and label args for cloud nodes
    for ((i=0; i<CLOUD_NODES_NUM; i++)); do
        if [ "$NO_RESOURCE_RESTRICTIONS" = false ]; then
            k3s_args+=("--k3s-arg" "--kubelet-arg=system-reserved=cpu=${CLOUD_SYSTEM_RESERVED_CPU},memory=${CLOUD_SYSTEM_RESERVED_MEMORY_KB}Ki@agent:${i}")
        fi
        for label in "${CLOUD_NODES_LABELS[@]}"; do
            cloud_labels+=("--k3s-node-label" "${label}@agent:$i")
        done
    done

    # Generate k3s-arg and label args for edge nodes
    for ((i=CLOUD_NODES_NUM; i<TOTAL_NODES; i++)); do
        if [ "$NO_RESOURCE_RESTRICTIONS" = false ]; then
            k3s_args+=("--k3s-arg" "--kubelet-arg=system-reserved=cpu=${EDGE_SYSTEM_RESERVED_CPU},memory=${EDGE_SYSTEM_RESERVED_MEMORY_KB}Ki@agent:${i}")
        fi
        for label in "${EDGE_NODES_LABELS[@]}"; do
            edge_labels+=("--k3s-node-label" "${label}@agent:$i")
        done
    done

    # Create the k3d cluster
    k3d cluster create "${CLUSTER_NAME}" "${K3D_CLUSTER_CREATE_ARGS[@]}" \
        "${k3s_args[@]}" \
        "${cloud_labels[@]}" "${edge_labels[@]}"

    # Wait for all pods to be in Running or Completed state
    wait_for_pods_ready

    if [ "$NO_MUBENCH" = false ]; then
        echo "Deploying MuBench..."
        # Start MuBench Container and deploy it
        start_mubench
        deploy_mubench
        # Wait for all pods to be in Running or Completed state
        wait_for_pods_ready
    else
        echo "Skipping MuBench deployment..."
    fi

    if [ "$NO_RESOURCE_RESTRICTIONS" = false ]; then
        echo "Applying docker resource restrictions..."
        # Set resource limits for cloud nodes containers
        for ((i=0; i<CLOUD_NODES_NUM; i++)); do
            agent_name="k3d-${CLUSTER_NAME}-agent-${i}"
            docker update --cpus="${CLOUD_NODES_CPU_CAPACITY}" --memory="${CLOUD_NODES_MEMORY_CAPACITY_GB}g" --memory-swap="${CLOUD_NODES_MEMORY_CAPACITY_GB}g" "${agent_name}"
        done

        # Set resource limits for edge nodes containers
        for ((i=0; i<EDGE_NODES_NUM; i++)); do
            agent_index=$((CLOUD_NODES_NUM + i))
            agent_name="k3d-${CLUSTER_NAME}-agent-${agent_index}"
            docker update --cpus="${EDGE_NODES_CPU_CAPACITY}" --memory="${EDGE_NODES_MEMORY_CAPACITY_GB}g" --memory-swap="${EDGE_NODES_MEMORY_CAPACITY_GB}g" "${agent_name}"
        done
    else 
        echo "Skipping docker resource restrictions..."
    fi


    if [ "$NO_NETWORK_RESTRICTIONS" = false ]; then
        echo "Applying network restrictions..."
        # Apply network restrictions for edge nodes
        for ((i=0; i<EDGE_NODES_NUM; i++)); do
            # Emulate low network restrictions for edge nodes
            apply_network_restrictions "${agent_name}" "eth0"
        done
    else 
        echo "Skipping network restrictions..."
    fi

    info
}

down(){
    k3d cluster delete "${CLUSTER_NAME}"
    if [ "$NO_MUBENCH" = false ]; then
        echo "Stoping MuBench"
        stop_mubench
    fi
}

info(){
    # Display allocatable resources and labels of agent nodes
    kubectl get nodes -o jsonpath="{range .items[*]}{.metadata.name} {'allocatable: memory='}{.status.allocatable.memory} {'cpu='}{.status.allocatable.cpu} {'labels='}{.metadata.labels}{'\n'}{end}" | grep "k3d-continuum-agent"
    for ((i=0; i<TOTAL_NODES; i++)); do
        agent_name="k3d-${CLUSTER_NAME}-agent-${i}"
        docker inspect --format='{{.Name}}: CPU={{.HostConfig.NanoCpus}} Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}}' "${agent_name}"
    done
}

# Check if no arguments were provided
if [ $# -eq 0 ]; then
    usage_error
fi

CMD=$1
shift 1 || true

if [ "${CMD}" = "init" ]; then
    init
elif [ "${CMD}" = "up" ]; then
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-resource-restrictions)
                NO_RESOURCE_RESTRICTIONS=true
                shift
                ;;
            --no-network-restrictions)
                NO_NETWORK_RESTRICTIONS=true
                shift
                ;;
            --no-mubench)
                NO_MUBENCH=true
                shift
                ;;
            *)
                usage_error
                ;;
        esac
    done
    up
elif [ "${CMD}" = "down" ]; then
    down
elif [ "${CMD}" = "info" ]; then
    info
else
    echo "Invalid command: ${CMD}"
    usage_error
fi
