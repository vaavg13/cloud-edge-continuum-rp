"""
Core functionality for generating work models.
"""

import random
import os
from typing import Dict, Any


class WorkModelGenerator:
    def __init__(self, request_method: str = "GET", databases_prefix: str = "db"):
        """
        Initialize the WorkModelGenerator.

        Args:
            request_method: The HTTP method to use for requests (default: "GET")
            databases_prefix: Prefix used to identify database services (default: "db")
        """
        self.request_method = request_method
        self.databases_prefix = databases_prefix

    @staticmethod
    def _select_internal_service(internal_services: Dict[str, Dict[str, Any]]) -> str:
        """
        Select exactly one service function according to the probability.

        Args:
            internal_services: Dictionary of internal services with their probabilities

        Returns:
            Selected function ID
        """
        internal_service_items = internal_services.items()
        random_extraction = random.random()
        
        p_total = sum(v["probability"] for v in internal_services.values())
        p_total = round(p_total, 10)
        
        prev_interval = 0
        for k, v in internal_services.items():
            if random_extraction <= prev_interval + v["probability"]/p_total:
                return k
            prev_interval += round(v["probability"]/p_total, 10)
        
        # Fallback to last service if rounding errors occur
        return list(internal_services.keys())[-1]

    def generate_work_model(self, 
                          service_graph: Dict[str, Any], 
                          workmodel_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a work model based on the service graph and parameters.

        Args:
            service_graph: Dictionary describing the service mesh architecture
            workmodel_params: Parameters for work model generation including function definitions

        Returns:
            Generated work model dictionary
        """
        work_model = {}
        override = workmodel_params.get("override", {}).get("value", {})

        # Extract internal services
        internal_services = {}
        internal_services_db = {}

        for k, w in workmodel_params.items():
            if w.get("type") != "function":
                continue

            tmp_dict = {
                "internal_service": {w["value"]["name"]: w["value"]["parameters"]},
                "request_method": self.request_method
            }

            # Add optional parameters if present
            for param in ["workers", "threads", "replicas", "cpu-limits", 
                         "cpu-requests", "memory-limits", "memory-requests"]:
                if param in w["value"]:
                    tmp_dict[param] = w["value"][param]

            # Categorize service based on recipient type
            recipient = w["value"].get("recipient")
            service_dict = {
                "string": tmp_dict,
                "probability": w["value"]["probability"]
            }

            if recipient == "database":
                internal_services_db[k] = service_dict
            elif recipient == "service":
                internal_services[k] = service_dict

        # Use service internals for DB if none specified
        if not internal_services_db:
            internal_services_db = internal_services

        try:
            # Generate work model for each vertex in service graph
            for vertex in service_graph:
                work_model[vertex] = {
                    'external_services': service_graph[vertex]['external_services']
                }

                # Select appropriate internal service based on vertex type
                if vertex.startswith(self.databases_prefix):
                    selected = self._select_internal_service(internal_services_db)
                    work_model[vertex].update(internal_services_db[selected]['string'])
                else:
                    selected = self._select_internal_service(internal_services)
                    work_model[vertex].update(internal_services[selected]['string'])

                # Apply overrides if specified
                if vertex in override:
                    if "sidecar" in override[vertex]:
                        work_model[vertex]["sidecar"] = override[vertex]["sidecar"]
                    if "function_id" in override[vertex]:
                        work_model[vertex].update(
                            internal_services[override[vertex]['function_id']]['string']
                        )

        except Exception as err:
            raise RuntimeError(f"Failed to generate work model: {err}")

        return work_model 