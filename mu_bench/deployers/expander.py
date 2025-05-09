import json
from copy import deepcopy
from collections import defaultdict

def _get_routing_zone(affinity_spec, default_zone="cloud"):
    """
    Determine a routing zone from an affinity_spec.
    If affinity_spec is "zone=some_value", returns "some_value".
    Otherwise, returns default_zone.
    """
    if isinstance(affinity_spec, str):
        parts = affinity_spec.split('=')
        if len(parts) == 2 and parts[0].strip() == "zone":
            return parts[1].strip()
    # Fallback for old dict format if needed, or extend for more complex parsing
    elif isinstance(affinity_spec, dict): # Handle existing dict format for zone
        return affinity_spec.get("zone", default_zone)
    return default_zone

def build_deployment_mappings(workmodel):
    """
    Build mappings for (logical_name, zone) -> deployment_name and logical_name -> list of (zone, deployment_name).
    """
    name_zone_to_deployment = {}
    logical_to_deployments = defaultdict(list)
    for svc_name, svc_conf in workmodel.items():
        deployments = svc_conf.get("deployments")
        if deployments:
            for dep in deployments:
                affinity_spec = dep.get("node_affinity")
                routing_zone = _get_routing_zone(affinity_spec) # Use helper
                name_zone_to_deployment[(svc_name, routing_zone)] = dep["name"]
                logical_to_deployments[svc_name].append((routing_zone, dep["name"]))
        else:
            affinity_spec = svc_conf.get("node_affinity")
            routing_zone = _get_routing_zone(affinity_spec, "cloud") # Use helper
            name_zone_to_deployment[(svc_name, routing_zone)] = svc_name
            logical_to_deployments[svc_name].append((routing_zone, svc_name))
    return name_zone_to_deployment, logical_to_deployments

def expand_single_deployment(svc_name, svc_conf, dep, zone, name_zone_to_deployment, logical_to_deployments):
    """
    Expand a single deployment, updating url and external_services references.
    """
    dep_conf = deepcopy(svc_conf)
    dep_conf.pop("deployments", None)
    dep_conf["node_affinity"] = dep.get("node_affinity") # This carries the actual affinity spec for the builder
    # Apply per-deployment overrides
    for k, v in dep.items():
        if k not in ("name", "node_affinity"):
            dep_conf[k] = v
    # Update url to match deployment name
    dep_conf["url"] = f"{dep['name']}.{dep_conf.get('namespace', 'default')}.svc.cluster.local"
    # Update external_services references
    if "external_services" in dep_conf:
        for ext in dep_conf["external_services"]:
            if "services" in ext:
                new_services = []
                for target in ext["services"]:
                    # 'zone' here is the routing_zone determined in build_deployment_mappings
                    target_name = name_zone_to_deployment.get((target, zone))
                    if not target_name:
                        target_name = name_zone_to_deployment.get((target, "cloud")) # Fallback to cloud
                    if not target_name and logical_to_deployments[target]: # Ensure list is not empty
                        target_name = logical_to_deployments[target][0][1] # Fallback to first available
                    if target_name:
                        new_services.append(target_name)
                    else:
                        # Handle case where target is not found, maybe log a warning or error
                        print(f"Warning: Could not resolve target service '{target}' for deployment '{dep['name']}' in zone '{zone}'.")
                ext["services"] = new_services
    return dep["name"], dep_conf

def expand_workmodel(workmodel):
    """
    Expand a workmodel with deployments into a flat dict with deployment-specific configs.
    """
    name_zone_to_deployment, logical_to_deployments = build_deployment_mappings(workmodel)
    expanded = {}
    for svc_name, svc_conf in workmodel.items():
        deployments = svc_conf.get("deployments")
        if deployments:
            for dep in deployments:
                # The 'zone' for expand_single_deployment should be the one used for routing.
                # This is derived from dep.get("node_affinity") inside build_deployment_mappings
                # and then used to find the correct (zone, dep_name) entry.
                # We need to ensure 'zone' passed to expand_single_deployment is this routing_zone.

                # Find the routing_zone that was used when populating name_zone_to_deployment for this dep
                # This logic assumes dep["name"] is unique across all services and zones for simplicity here.
                # A more robust way might involve passing the routing_zone directly from build_deployment_mappings
                # or re-calculating it here.
                # For now, let's re-calculate it to be explicit.
                dep_affinity_spec = dep.get("node_affinity")
                current_dep_routing_zone = _get_routing_zone(dep_affinity_spec)

                dep_name, dep_conf = expand_single_deployment(
                    svc_name, svc_conf, dep, current_dep_routing_zone, name_zone_to_deployment, logical_to_deployments
                )
                expanded[dep_name] = dep_conf
        else:
            # No deployments, treat as global
            conf = deepcopy(svc_conf)
            # node_affinity is already part of svc_conf, so it's in 'conf'
            # conf["node_affinity"] will be whatever is in svc_conf.get("node_affinity")
            
            # Determine routing_zone for external_services resolution
            svc_affinity_spec = svc_conf.get("node_affinity")
            routing_zone_for_svc = _get_routing_zone(svc_affinity_spec, "cloud")

            conf["url"] = f"{svc_name}.{conf.get('namespace', 'default')}.svc.cluster.local"
            if "external_services" in conf:
                for ext in conf["external_services"]:
                    if "services" in ext:
                        new_services = []
                        for target in ext["services"]:
                            target_name = name_zone_to_deployment.get((target, routing_zone_for_svc))
                            if not target_name:
                                target_name = name_zone_to_deployment.get((target, "cloud")) # Fallback to cloud
                            if not target_name and logical_to_deployments[target]: # Ensure list is not empty
                                target_name = logical_to_deployments[target][0][1] # Fallback to first available
                            if target_name:
                                new_services.append(target_name)
                            else:
                                print(f"Warning: Could not resolve target service '{target}' for service '{svc_name}' in zone '{routing_zone_for_svc}'.")
                        ext["services"] = new_services
            expanded[svc_name] = conf

    return expanded 