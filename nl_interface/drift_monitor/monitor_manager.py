"""
Monitor Manager for Drift Monitor
Main orchestrator that manages multiple monitoring loops and coordinates the monitoring system.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone

from .config_schema import DriftMonitorConfig, ThresholdConfig
from .metric_evaluator import MetricEvaluator, MetricViolation

logger = logging.getLogger(__name__)

class DriftMonitor:
    """A simple drift monitor for a single monitoring configuration - pure monitoring only."""
    
    def __init__(self, config: DriftMonitorConfig, violation_callback: Optional[Callable] = None):
        self.config = config
        self.evaluator = MetricEvaluator(config.prometheus_url)
        self.violation_callback = violation_callback  # Optional callback for violations
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._is_running = False
        
    async def _monitor_worker(self):
        """Main worker loop for monitoring."""
        logger.info(f"Starting drift monitor: {self.config.loop_id}")
        
        while not self._stop_event.is_set():
            try:
                start_time = time.time()
                
                # Skip if disabled
                if not self.config.enabled:
                    await asyncio.sleep(self.config.check_interval_seconds)
                    continue
                
                # Evaluate metrics against thresholds
                violations = self.evaluator.evaluate_loop(self.config)
                
                # Handle violations if callback provided
                if violations:
                    logger.warning(f"Monitor {self.config.loop_id}: Found {len(violations)} violations")
                    
                    if self.violation_callback:
                        try:
                            await self.violation_callback(violations)
                        except Exception as e:
                            logger.error(f"Error in violation callback: {e}")
                else:
                    logger.debug(f"Monitor {self.config.loop_id}: No violations detected")
                
                # Calculate how long to sleep
                execution_time = time.time() - start_time
                sleep_time = max(0, self.config.check_interval_seconds - execution_time)
                
                if sleep_time > 0:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_time)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in drift monitor {self.config.loop_id}: {e}")
                # Wait a bit before retrying to avoid spam
                await asyncio.sleep(min(60, self.config.check_interval_seconds))
        
        logger.info(f"Stopped drift monitor: {self.config.loop_id}")
    
    async def start(self):
        """Start the drift monitor."""
        if self._is_running:
            logger.warning(f"Monitor {self.config.loop_id} is already running")
            return
        
        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_worker())
        self._is_running = True
        logger.info(f"Started drift monitor: {self.config.loop_id}")
    
    async def stop(self):
        """Stop the drift monitor."""
        if not self._is_running:
            return
        
        logger.info(f"Stopping drift monitor: {self.config.loop_id}")
        self._stop_event.set()
        
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning(f"Monitor {self.config.loop_id} did not stop gracefully, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        
        self._is_running = False
        logger.info(f"Stopped drift monitor: {self.config.loop_id}")
    
    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._is_running

    async def check_once(self) -> Dict[str, Any]:
        """Check metrics once and return results without starting continuous monitoring."""
        try:
            violations = self.evaluator.evaluate_loop(self.config)
            
            result = {
                "violations_found": len(violations),
                "violations": [
                    {
                        "metric_type": v.threshold.metric_type.value,
                        "actual_value": v.actual_value,
                        "threshold_value": v.threshold.threshold_value,
                        "operator": v.threshold.operator.value,
                        "description": v.threshold.description
                    } for v in violations
                ]
            }
            
            # Call violation callback if provided
            if violations and self.violation_callback:
                try:
                    callback_result = await self.violation_callback(violations)
                    result["callback_result"] = callback_result
                except Exception as e:
                    result["callback_error"] = str(e)
            
            return result
                
        except Exception as e:
            return {"error": str(e)}

    async def cleanup(self):
        """Cleanup resources."""
        await self.stop()


def create_monitor_with_agent_actions(config: DriftMonitorConfig, intent_template: str = None) -> DriftMonitor:
    """
    Create a DriftMonitor with ActionExecutor as violation callback.
    This eliminates the need for the bridge layer.
    
    Args:
        config: DriftMonitorConfig for the monitor
        intent_template: Simple template for agent intent (optional)
                        Can use variables like: {namespace}, {metric_type}, {metric_value}, etc.
        
    Returns:
        DriftMonitor instance with agent actions enabled
    """
    from ..agent.action_executor import ActionExecutor
    
    # Create action executor with simple intent template
    action_executor = ActionExecutor(intent_template)
    
    # Use ActionExecutor.call_agent_for_violations as the violation callback
    return DriftMonitor(config, violation_callback=action_executor.call_agent_for_violations) 