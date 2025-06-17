"""
Action Executor for Drift Monitor
Executes actions when metric threshold violations are detected.
"""

import asyncio
import logging
import json

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from ..drift_monitor.metric_evaluator import MetricViolation
from .agent import KubernetesAgent

logger = logging.getLogger(__name__)

DEFAULT_INTENT_TEMPLATE = """
Handle {metric_type} issue in namespace {namespace}: 
current value is {metric_value}, threshold is {threshold_value}
"""

class ActionExecutor:
    """
    Simple executor that calls the Kubernetes agent when violations occur.
    
    Prompt Composition:
    1. Agent gets its default system prompt (about available tools, etc.)
    2. We pass user intent (from config) + violation context as the user message
    3. Agent decides what tools to use based on intent + context
    """
    
    def __init__(self, intent_template: str = DEFAULT_INTENT_TEMPLATE):
        """
        Initialize with simple intent template.
        """

        self.intent_template = intent_template
        self._agent_instance = None
        
    async def _get_agent_instance(self) -> KubernetesAgent:
        """Get or create agent instance."""
        if self._agent_instance is None:
            self._agent_instance = KubernetesAgent()
            await self._agent_instance.initialize()
        return self._agent_instance
    
    def _build_intent_and_context(self, violations: List[MetricViolation]) -> tuple[str, Dict[str, Any]]:
        """
        Build the intent message and context from violations.
        """
        if not violations:
            return "No violations detected", {}
        
        # Use first violation for template formatting
        v = violations[0]
        
        # Format the intent template
        intent = self.intent_template.format(
            namespace=v.namespace,
            pod_name=v.pod_name or "all_pods",
            metric_type=v.threshold.metric_type.value,
            metric_value=v.actual_value,
            threshold_value=v.threshold.threshold_value,
            operator=v.threshold.operator.value,
            unit=v.threshold.unit or "",
            loop_id=v.loop_id,
            violation_count=len(violations)
        )
        
        # Build structured context for agent
        context = {
            "violations": [
                {
                    "loop_id": violation.loop_id,
                    "namespace": violation.namespace,
                    "pod_name": violation.pod_name,
                    "metric_type": violation.threshold.metric_type.value,
                    "actual_value": violation.actual_value,
                    "threshold_value": violation.threshold.threshold_value,
                    "operator": violation.threshold.operator.value,
                    "unit": violation.threshold.unit,
                    "description": violation.threshold.description,
                    "timestamp": violation.timestamp.isoformat()
                } for violation in violations
            ],
            "summary": {
                "total_violations": len(violations),
                "namespaces": list(set(v.namespace for v in violations)),
                "metric_types": list(set(v.threshold.metric_type.value for v in violations)),
                "action_timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return intent, context
    
    async def call_agent_for_violations(self, violations: List[MetricViolation]) -> Dict[str, Any]:
        """
        Execute agent call for violations.
        
        Flow:
        1. Build intent message from template + violation data
        2. Build structured context with all violation details  
        3. Agent gets default system prompt + our intent + context
        4. Agent uses its tools to handle the situation
        
        Args:
            violations: List of metric violations detected
            
        Returns:
            Dict with execution results
        """
        try:
            agent = await self._get_agent_instance()
            
            # Build the intent and context (this is the key part!)
            intent, context = self._build_intent_and_context(violations)
            
            logger.info(f"🚨 VIOLATION DETECTED! Calling agent with intent: {intent}")
            print(f"🚨 VIOLATION DETECTED! Calling agent...")
            print(f"   Intent: {intent}")
            for v in violations:
                print(f"   - {v.namespace}/{v.pod_name}: {v.threshold.metric_type.value} = {v.actual_value} {v.threshold.operator.value} {v.threshold.threshold_value}")
            
            # Add timeout to prevent hanging
            actions_taken = await asyncio.wait_for(
                agent.agent_loop(intent, context), 
                timeout=120  # 2 minutes timeout
            )
            
            print(f"✅ Agent actions completed: {actions_taken.get('summary', 'No summary available')}")
            
            return {
                "status": "success",
                "intent": intent,
                "actions_taken": actions_taken,
                "violations_count": len(violations)
            }
            
        except asyncio.TimeoutError:
            error_msg = "Agent call timed out after 2 minutes"
            logger.error(error_msg)
            print(f"⏰ {error_msg}")
            return {
                "status": "timeout",
                "error": error_msg,
                "intent": self.intent_template,
                "violations_count": len(violations)
            }
        except Exception as e:
            logger.error(f"Error executing agent call: {e}")
            print(f"❌ Agent error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "intent": self.intent_template,
                "violations_count": len(violations)
            }
    
    async def cleanup(self):
        """Cleanup resources."""
        if self._agent_instance:
            await self._agent_instance.cleanup() 