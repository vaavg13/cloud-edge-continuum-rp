"""
Monitoring Orchestrator - Coordinates between drift monitoring and agent actions.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import time

from ..shared.types import MetricViolation
from ..drift_monitor.monitor_manager import DriftMonitor
from ..agent.agent import KubernetesAgent
from ..agent.violation_handler import ViolationHandler

logger = logging.getLogger(__name__)

@dataclass
class OrchestratorConfig:
    """Configuration for the monitoring orchestrator."""
    check_interval_seconds: int = 60
    max_concurrent_agents: int = 1
    agent_timeout_seconds: int = 120
    agent_cooldown_seconds: int = 300  # 5 minutes cooldown between agent spawns
    enable_violation_logging: bool = True

class MonitoringOrchestrator:
    """
    Orchestrates the monitoring and agent execution flow.
    Coordinates between DriftMonitor (detection) and KubernetesAgent (response).
    """
    
    def __init__(self, 
                 monitor: DriftMonitor, 
                 config: Optional[OrchestratorConfig] = None,
                 intent_template: str = None,
                 agent_config: Optional[Dict[str, Any]] = None):
        self.monitor = monitor
        self.config = config or OrchestratorConfig()
        self.intent_template = intent_template or (
            "Handle {metric_type} issue in namespace {namespace} (deployment: {deployment_name}): "
            "current value is {metric_value}, threshold is {threshold_value}"
        )
        
        # Create violation handler
        self.violation_handler = ViolationHandler(
            intent_template=self.intent_template,
            agent_config=agent_config or {}
        )
        
        self._agent_semaphore = asyncio.Semaphore(self.config.max_concurrent_agents)
        self._last_agent_execution_time = 0  # Track last agent execution for cooldown
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start_monitoring(self):
        """Start the orchestrated monitoring loop."""
        if self._is_running:
            logger.warning("Orchestrator is already running")
            return
            
        logger.info("Starting monitoring orchestrator")
        self._is_running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        
    async def stop_monitoring(self):
        """Stop the orchestrated monitoring loop."""
        if not self._is_running:
            return
            
        logger.info("Stopping monitoring orchestrator")
        self._is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    async def check_and_handle_violations_once(self) -> Dict[str, Any]:
        """
        Check for violations once and handle the first one only.
        Returns results without starting continuous monitoring.
        """
        try:
            # Get violations from monitor
            violations = await self.monitor.check_once()
            
            if violations.get("error"):
                return {"error": violations["error"], "violations_handled": 0}
                
            violation_objects = violations.get("violations", [])
            
            if not violation_objects:
                return {
                    "status": "no_violations",
                    "violations_found": 0,
                    "violations_handled": 0
                }
            
            # Only process the first violation
            first_violation = violation_objects[0]
            
            # Check cooldown period
            current_time = time.time()
            time_since_last_execution = current_time - self._last_agent_execution_time
            
            if time_since_last_execution < self.config.agent_cooldown_seconds:
                remaining_cooldown = self.config.agent_cooldown_seconds - time_since_last_execution
                logger.info(f"Agent in cooldown for {remaining_cooldown:.1f} more seconds")
                return {
                    "status": "cooldown",
                    "violations_found": len(violation_objects),
                    "violations_handled": 0,
                    "cooldown_remaining_seconds": remaining_cooldown
                }
            
            # Handle the first violation
            try:
                result = await self._handle_single_violation(first_violation)
                self._last_agent_execution_time = current_time  # Update last execution time
                
                return {
                    "status": "completed",
                    "violations_found": len(violation_objects),
                    "violations_handled": 1,
                    "violations_skipped": len(violation_objects) - 1,
                    "result": result
                }
                
            except Exception as e:
                logger.error(f"Error handling violation: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "violations_found": len(violation_objects),
                    "violations_handled": 0
                }
            
        except Exception as e:
            logger.error(f"Error in check_and_handle_violations_once: {e}")
            return {"error": str(e), "violations_handled": 0}
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        logger.info("Starting monitoring loop")
        
        while self._is_running:
            try:
                start_time = asyncio.get_event_loop().time()
                
                # Check for violations
                result = await self.check_and_handle_violations_once()
                
                if result.get("error"):
                    logger.error(f"Monitoring error: {result['error']}")
                elif result.get("status") == "cooldown":
                    logger.debug(f"Agent in cooldown for {result.get('cooldown_remaining_seconds', 0):.1f}s")
                elif result.get("violations_found", 0) > 0:
                    handled = result.get("violations_handled", 0)
                    skipped = result.get("violations_skipped", 0)
                    logger.info(f"Found {result['violations_found']} violations: "
                               f"handled {handled}, skipped {skipped}")
                
                # Calculate sleep time
                execution_time = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.config.check_interval_seconds - execution_time)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(min(60, self.config.check_interval_seconds))
        
        logger.info("Monitoring loop stopped")
    
    async def _handle_single_violation(self, violation: MetricViolation) -> Dict[str, Any]:
        """Handle a single violation through the violation handler."""
        async with self._agent_semaphore:
            if self.config.enable_violation_logging:
                self._log_violation(violation)
            
            try:
                # Execute through violation handler with timeout
                result = await asyncio.wait_for(
                    self.violation_handler.handle_violation(violation, self.intent_template),
                    timeout=self.config.agent_timeout_seconds
                )
                
                logger.info(f"Violation handling completed: {result.get('status', 'unknown')}")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Violation handling timeout after {self.config.agent_timeout_seconds}s"
                logger.error(error_msg)
                return {"status": "timeout", "error": error_msg}
                
            except Exception as e:
                error_msg = f"Violation handling error: {e}"
                logger.error(error_msg)
                return {"status": "error", "error": error_msg}
    
    def _log_violation(self, violation: MetricViolation):
        """Log violation details."""
        print(f"\n🚨 VIOLATION DETECTED")
        print(f"   Namespace: {violation.namespace}")
        print(f"   Deployment: {violation.deployment_name}")
        print(f"   Metric: {violation.metric_type.value}")
        print(f"   Current: {violation.actual_value} {violation.unit or ''}")
        print(f"   Threshold: {violation.operator.value} {violation.threshold_value}")
        print(f"   Time: {violation.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        if violation.description:
            print(f"   Description: {violation.description}")
        print(f"🤖 Starting agent execution...")
        print("=" * 50)