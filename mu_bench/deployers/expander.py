import json
from copy import deepcopy
from collections import defaultdict

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
                zone = dep.get("node_affinity", {}).get("zone")
                name_zone_to_deployment[(svc_name, zone)] = dep["name"]
                logical_to_deployments[svc_name].append((zone, dep["name"]))
        else:
            zone = svc_conf.get("node_affinity", {}).get("zone", "cloud")
            name_zone_to_deployment[(svc_name, zone)] = svc_name
            logical_to_deployments[svc_name].append((zone, svc_name))
    return name_zone_to_deployment, logical_to_deployments

def expand_single_deployment(svc_name, svc_conf, dep, zone, name_zone_to_deployment, logical_to_deployments):
    """
    Expand a single deployment, updating url and external_services references.
    """
    dep_conf = deepcopy(svc_conf)
    dep_conf.pop("deployments", None)
    dep_conf["node_affinity"] = dep.get("node_affinity")
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
                    # Prefer same-zone deployment if available, else fallback to cloud, else first available
                    target_name = name_zone_to_deployment.get((target, zone))
                    if not target_name:
                        target_name = name_zone_to_deployment.get((target, "cloud"))
                    if not target_name:
                        target_name = logical_to_deployments[target][0][1]
                    new_services.append(target_name)
                ext["services"] = new_services
    return dep["name"], dep_conf

def expand_workmodel(workmodel, save_to_file="expanded_workmodel.json"):
    """
    Expand a workmodel with deployments into a flat dict with deployment-specific configs.
    Saves the expanded workmodel to a file if specified.
    """
    name_zone_to_deployment, logical_to_deployments = build_deployment_mappings(workmodel)
    expanded = {}
    for svc_name, svc_conf in workmodel.items():
        deployments = svc_conf.get("deployments")
        if deployments:
            for dep in deployments:
                zone = dep.get("node_affinity", {}).get("zone")
                dep_name, dep_conf = expand_single_deployment(
                    svc_name, svc_conf, dep, zone, name_zone_to_deployment, logical_to_deployments
                )
                expanded[dep_name] = dep_conf
        else:
            # No deployments, treat as global
            zone = svc_conf.get("node_affinity", {}).get("zone", "cloud")
            conf = deepcopy(svc_conf)
            conf["url"] = f"{svc_name}.{conf.get('namespace', 'default')}.svc.cluster.local"
            if "external_services" in conf:
                for ext in conf["external_services"]:
                    if "services" in ext:
                        new_services = []
                        for target in ext["services"]:
                            target_name = name_zone_to_deployment.get((target, zone))
                            if not target_name:
                                target_name = name_zone_to_deployment.get((target, "cloud"))
                            if not target_name:
                                target_name = logical_to_deployments[target][0][1]
                            new_services.append(target_name)
                        ext["services"] = new_services
            expanded[svc_name] = conf
    if save_to_file:
        with open(save_to_file, "w") as f:
            json.dump(expanded, f, indent=2)
    return expanded 