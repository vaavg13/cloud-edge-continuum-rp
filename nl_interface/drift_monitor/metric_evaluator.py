"""
Metric Evaluator for Drift Monitor
Evaluates metrics against configured thresholds and detects violations.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import logging
from .config_schema import ThresholdConfig, DriftMonitorConfig  
from ..shared.types import MetricType, ComparisonOperator, MetricViolation
from ..shared.prometheus_client import PrometheusMetricsTool

logger = logging.getLogger(__name__)



class ViolationTracker:
    """Tracks consecutive violations for each monitoring loop."""
    
    def __init__(self):
        self._violations: Dict[str, List[MetricViolation]] = {}
        
    def add_violation(self, violation: MetricViolation) -> int:
        """Add a violation and return consecutive count."""
        key = f"{violation.loop_id}_{violation.metric_type.value}"
        if key not in self._violations:
            self._violations[key] = []
        
        self._violations[key].append(violation)
        return len(self._violations[key])
    
    def clear_violations(self, loop_id: str, metric_type: MetricType):
        """Clear violations for a specific loop and metric type."""
        key = f"{loop_id}_{metric_type.value}"
        if key in self._violations:
            del self._violations[key]
    
    def get_consecutive_count(self, loop_id: str, metric_type: MetricType) -> int:
        """Get consecutive violation count for a loop and metric type."""
        key = f"{loop_id}_{metric_type.value}"
        return len(self._violations.get(key, []))

class MetricEvaluator:
    """Evaluates metrics against thresholds and detects violations."""
    
    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_tool = PrometheusMetricsTool(prometheus_url)
        self.violation_tracker = ViolationTracker()
        
    def _compare_values(self, actual: float, expected: float, operator: ComparisonOperator) -> bool:
        """Compare two values using the specified operator."""
        import math
        
        # Handle NaN values - they should never trigger violations
        if math.isnan(actual) or math.isnan(expected):
            return False
            
        if operator == ComparisonOperator.GREATER_THAN:
            return actual > expected
        elif operator == ComparisonOperator.LESS_THAN:
            return actual < expected
        elif operator == ComparisonOperator.GREATER_EQUAL:
            return actual >= expected
        elif operator == ComparisonOperator.LESS_EQUAL:
            return actual <= expected
        elif operator == ComparisonOperator.EQUAL:
            return abs(actual - expected) < 1e-6  # Float comparison with tolerance
        elif operator == ComparisonOperator.NOT_EQUAL:
            return abs(actual - expected) >= 1e-6
        else:
            raise ValueError(f"Unsupported operator: {operator}")
    
    def _get_metric_values(self, metric_type: MetricType, namespace: str, 
                          deployment_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current metric values from Prometheus."""
        try:
            if metric_type == MetricType.POD_CPU:
                result = self.prometheus_tool.get_current_pod_cpu(namespace)
            elif metric_type == MetricType.POD_MEMORY:
                result = self.prometheus_tool.get_current_pod_memory(namespace)
            elif metric_type == MetricType.NODE_CPU:
                result = self.prometheus_tool.get_current_node_cpu()
            elif metric_type == MetricType.NODE_MEMORY:
                result = self.prometheus_tool.get_current_node_memory()
            elif metric_type == MetricType.ISTIO_LATENCY:
                result = self.prometheus_tool.get_current_istio_latency(namespace)
            else:
                logger.error(f"Unsupported metric type: {metric_type}")
                return []
            
            if result.get("error"):
                logger.error(f"Error getting {metric_type} metrics: {result['error']}")
                return []
            
            metrics = result.get("data", [])
            
            # Filter by deployment name if specified (filter pods that belong to the deployment)
            if deployment_name and metric_type in [MetricType.POD_CPU, MetricType.POD_MEMORY]:
                # For pod metrics, filter by pods that start with deployment name
                metrics = [m for m in metrics if m.get("pod", "").startswith(deployment_name)]
            elif deployment_name and metric_type == MetricType.ISTIO_LATENCY:
                # For istio metrics, workload corresponds to deployment name
                metrics = [m for m in metrics if m.get("workload") == deployment_name]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting {metric_type} metrics: {e}")
            return []
    
    def _extract_metric_value(self, metric_data: Dict[str, Any], metric_type: MetricType) -> float:
        """Extract the numeric value from metric data."""
        if metric_type == MetricType.POD_CPU:
            return metric_data.get("cpu_cores_used", 0.0)
        elif metric_type == MetricType.POD_MEMORY:
            # Convert to MB for easier threshold setting
            return metric_data.get("memory_usage_bytes", 0) / (1024 * 1024)
        elif metric_type == MetricType.NODE_CPU:
            return metric_data.get("cpu_cores_used", 0.0)
        elif metric_type == MetricType.NODE_MEMORY:
            # Convert to MB for easier threshold setting
            return metric_data.get("memory_working_set_bytes", 0) / (1024 * 1024)
        elif metric_type == MetricType.ISTIO_LATENCY:
            return metric_data.get("p95_latency_ms", 0.0)
        else:
            return 0.0
    
    def evaluate_loop(self, loop_config: DriftMonitorConfig) -> List[MetricViolation]:
        """Evaluate all thresholds for a monitoring loop."""
        violations = []
        now = datetime.now(timezone.utc)
        
        for threshold in loop_config.thresholds:
            # Get current metric values
            metric_values = self._get_metric_values(
                threshold.metric_type, 
                loop_config.namespace, 
                loop_config.deployment_name
            )
            
            if not metric_values:
                logger.warning(f"No metric values found for {threshold.metric_type} in "
                             f"namespace {loop_config.namespace}")
                continue
            
            # Check each metric value against threshold
            for metric_data in metric_values:
                actual_value = self._extract_metric_value(metric_data, threshold.metric_type)
                
                if self._compare_values(actual_value, threshold.threshold_value, threshold.operator):
                    # This is a violation
                    violation = MetricViolation(
                        loop_id=loop_config.loop_id,
                        namespace=loop_config.namespace,
                        deployment_name=loop_config.deployment_name or metric_data.get("workload") or metric_data.get("pod", "").split("-")[0],
                        metric_type=threshold.metric_type,
                        actual_value=actual_value,
                        threshold_value=threshold.threshold_value,
                        operator=threshold.operator,
                        unit=threshold.unit,
                        description=threshold.description,
                        timestamp=now,
                        consecutive_violations=threshold.consecutive_violations
                    )
                    
                    # Track consecutive violations
                    consecutive_count = self.violation_tracker.add_violation(violation)
                    
                    # Only add to violations if we've reached the required consecutive count
                    if consecutive_count >= threshold.consecutive_violations:
                        violation.consecutive_violations = consecutive_count
                        violations.append(violation)
                        logger.warning(f"Threshold violation detected: {violation}")
                else:
                    # Clear violations if metric is back to normal
                    self.violation_tracker.clear_violations(loop_config.loop_id, threshold.metric_type)
        
        return violations
    
    def get_current_metrics_summary(self, namespace: str, deployment_name: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of current metrics for a namespace/deployment."""
        summary = {
            "namespace": namespace,
            "deployment_name": deployment_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {}
        }
        
        # Get all metric types
        for metric_type in MetricType:
            try:
                values = self._get_metric_values(metric_type, namespace, deployment_name)
                if values:
                    # Aggregate values if multiple pods/nodes
                    if metric_type in [MetricType.POD_CPU, MetricType.POD_MEMORY]:
                        total_value = sum(self._extract_metric_value(v, metric_type) for v in values)
                        avg_value = total_value / len(values)
                        summary["metrics"][metric_type.value] = {
                            "total": round(total_value, 3),
                            "average": round(avg_value, 3),
                            "count": len(values),
                            "individual_values": [
                                {
                                    "pod": v.get("pod", "unknown"),
                                    "value": round(self._extract_metric_value(v, metric_type), 3)
                                } for v in values
                            ]
                        }
                    elif metric_type == MetricType.ISTIO_LATENCY:
                        avg_latency = sum(self._extract_metric_value(v, metric_type) for v in values) / len(values)
                        max_latency = max(self._extract_metric_value(v, metric_type) for v in values)
                        summary["metrics"][metric_type.value] = {
                            "average_ms": round(avg_latency, 2),
                            "max_ms": round(max_latency, 2),
                            "count": len(values),
                            "individual_values": [
                                {
                                    "workload": v.get("workload", "unknown"),
                                    "latency_ms": round(self._extract_metric_value(v, metric_type), 2)
                                } for v in values
                            ]
                        }
                    else:
                        # Node metrics
                        summary["metrics"][metric_type.value] = {
                            "values": [
                                {
                                    "node": v.get("node", "unknown"),
                                    "value": round(self._extract_metric_value(v, metric_type), 3)
                                } for v in values
                            ]
                        }
            except Exception as e:
                logger.error(f"Error getting {metric_type} summary: {e}")
                summary["metrics"][metric_type.value] = {"error": str(e)}
        
        return summary 