"""
Violation Handler for Drift Monitor
Handles metric violations by executing appropriate agent actions.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from ..shared.types import MetricViolation
from .agent import KubernetesAgent

logger = logging.getLogger(__name__)

DEFAULT_INTENT_TEMPLATE = """
Handle {metric_type} issue in namespace {namespace} (deployment: {deployment_name}): 
current value is {metric_value}, threshold is {threshold_value}
"""

class ViolationHandler:
    """Handles violations by formatting intent and executing agent."""
    
    def __init__(self, intent_template: str = DEFAULT_INTENT_TEMPLATE, agent_config: Optional[Dict[str, Any]] = None):
        """
        Initialize with intent template and agent config.
        
        Args:
            intent_template: Template for agent intent message
            agent_config: Configuration dict for the agent (optional)
        """
        self.intent_template = intent_template
        self.agent_config = agent_config or {}
        self._agent_instance = None
        self._agent_lock = asyncio.Lock()
        
        logger.info("ViolationHandler initialized")
        
    async def _get_agent_instance(self) -> KubernetesAgent:
        """Get or create agent instance."""
        async with self._agent_lock:
            if self._agent_instance is None:
                self._agent_instance = KubernetesAgent(config=self.agent_config)
                await self._agent_instance.initialize()
        return self._agent_instance
    
    async def handle_violation(self, violation: MetricViolation, intent_template: str = None) -> Dict[str, Any]:
        """
        Handle a single violation directly.
        
        Args:
            violation: MetricViolation to handle
            intent_template: Template for building intent message (optional)
            
        Returns:
            Dict with execution results
        """
        agent = await self._get_agent_instance()
        
        # Use provided template or instance default
        template = intent_template or self.intent_template
        
        # Build intent from template
        intent = template.format(
            namespace=violation.namespace,
            deployment_name=violation.deployment_name or "all_deployments",
            metric_type=violation.metric_type.value,
            metric_value=violation.actual_value,
            threshold_value=violation.threshold_value,
            operator=violation.operator.value,
            unit=violation.unit or "",
            loop_id=getattr(violation, 'loop_id', 'unknown')
        )
        
        # Build context for agent
        context = {
            "violation": {
                "loop_id": getattr(violation, 'loop_id', 'unknown'),
                "namespace": violation.namespace,
                "deployment_name": violation.deployment_name,
                "metric_type": violation.metric_type.value,
                "actual_value": violation.actual_value,
                "threshold_value": violation.threshold_value,
                "operator": violation.operator.value,
                "unit": violation.unit,
                "description": violation.description,
                "timestamp": violation.timestamp.isoformat()
            }
        }
        
        try:
            # Execute agent loop
            actions_taken = await agent.agent_loop(intent, context)
            
            logger.info(f"Handled violation: {violation.metric_type.value} in {violation.namespace}")
            
            return {
                "status": "success",
                "intent": intent,
                "actions_taken": actions_taken,
                "violation_details": {
                    "namespace": violation.namespace,
                    "deployment_name": violation.deployment_name,
                    "metric_type": violation.metric_type.value,
                    "actual_value": violation.actual_value,
                    "threshold_value": violation.threshold_value
                }
            }
            
        except Exception as e:
            error_msg = f"Error handling violation: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "intent": intent,
                "error": error_msg
            }
    
    async def cleanup(self):
        """Cleanup agent resources."""
        logger.info("Cleaning up ViolationHandler...")
        
        if self._agent_instance:
            try:
                await self._agent_instance.cleanup()
            except Exception as e:
                logger.error(f"Error during agent cleanup: {e}")
            finally:
                self._agent_instance = None
        
        logger.info("ViolationHandler cleanup completed")

# Backward compatibility
ActionExecutor = ViolationHandler 