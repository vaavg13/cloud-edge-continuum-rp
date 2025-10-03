"""
Core functionality for generating service graphs.
"""

import random
from typing import Dict, Any, List, Optional
from igraph import Graph, plot

class ServiceGraphGenerator:
    def __init__(self):
        """Initialize the ServiceGraphGenerator."""
        pass

    @staticmethod
    def _select_db(dbs: Dict[str, float]) -> str:
        """
        Select a database based on probability distribution.

        Args:
            dbs: Dictionary mapping database names to their probabilities

        Returns:
            Selected database name
        """
        random_extraction = random.random()
        p_total = sum(dbs.values())
        p_total = round(p_total, 10)
        
        prev_interval = 0
        for db_name, prob in dbs.items():
            if random_extraction <= prev_interval + prob/p_total:
                return db_name
            prev_interval += round(prob/p_total, 10)
        
        # Fallback to last database if rounding errors occur
        return list(dbs.keys())[-1]

    @staticmethod
    def _get_probability(graph_params: Dict[str, Any]) -> float:
        """
        Get service probability based on the model specified in parameters.

        Args:
            graph_params: Graph generation parameters

        Returns:
            Probability value
        """
        try:
            if "service_probability" in graph_params:
                prob_params = graph_params["service_probability"]
                if prob_params["model"] == "const":
                    return float(prob_params["params"]["value"])
                if prob_params["model"] == "random":
                    return round(random.random(), 3)
        except Exception as err:
            raise RuntimeError(f"Error in service_probability: {err}")
        
        return 1.0

    def generate_service_graph(self,
                             graph_params: Dict[str, Any],
                             output_path: Optional[str] = None,
                             output_file_png: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a service graph based on the provided parameters.

        Args:
            graph_params: Parameters for graph generation including:
                - vertices: Number of vertices
                - power: Power parameter for Barabasi graph
                - zero_appeal: Zero appeal parameter for Barabasi graph
                - external_service_groups: Number of external service groups
                - seq_len: Sequence length
                - dbs: Optional database configuration
            output_path: Optional path to save visualization
            output_file_png: Optional filename for visualization

        Returns:
            Generated service graph dictionary
        """
        # Create Barabasi graph
        g = Graph.Barabasi(
            n=graph_params["vertices"],
            power=graph_params["power"],
            m=1,
            zero_appeal=graph_params["zero_appeal"],
            directed=True
        )
        g.vs["label"] = list(range(graph_params["vertices"]))

        # Reverse edges to match desired direction
        edges = g.get_edgelist()
        g.delete_edges(edges)
        g.add_edges([(edge[1], edge[0]) for edge in edges])

        # Initialize service graph
        service_graph = {}
        graph_added_dbs = []

        # Process each vertex
        for vertex in range(graph_params["vertices"]):
            service_list = []
            current_service_group = 0

            # Process adjacent vertices
            for service_id in g.get_adjlist()[vertex]:
                if len(service_list) == current_service_group:
                    service_list.append({
                        "seq_len": graph_params["seq_len"],
                        "services": [],
                        "probabilities": {}
                    })

                service_list[current_service_group]["services"].append(f"s{service_id}")
                service_list[current_service_group]["probabilities"][f"s{service_id}"] = self._get_probability(graph_params)
                current_service_group = (current_service_group + 1) % graph_params["external_service_groups"]

            service_graph[f"s{vertex}"] = {'external_services': service_list}

            # Handle database connections if specified
            if "dbs" in graph_params and graph_params["dbs"]:
                selected_db = self._select_db(graph_params["dbs"])
                if selected_db == "nodb":
                    continue

                if selected_db not in graph_added_dbs:
                    graph_added_dbs.append(selected_db)
                    g.add_vertices(1)
                    service_graph[selected_db] = {'external_services': []}

                new_vertex = g.vcount() - 1
                g.add_edges([(vertex, new_vertex)])
                service_graph[f"s{vertex}"]['external_services'].append({
                    'seq_len': 1,
                    "services": [selected_db]
                })

        # Generate visualization if path provided
        if output_path and output_file_png:
            g.vs["label"] = list(range(graph_params["vertices"])) + graph_added_dbs
            g.vs["size"] = 35
            plot(g, f"{output_path}/{output_file_png}")

        return service_graph 