#!/usr/bin/env python3
"""
Main Agent Loop for Kubernetes Operations
Based on the template provided by the user, adapted for MCP Kubernetes operations.
"""

import asyncio
import json
import time
import random
import os
import openai
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from .mcp_client import MCPClient
from .tool_schemas import get_kubernetes_function_schemas
from .system_prompt_v2 import get_system_prompt
from .reasoning_prompts import get_reasoning_summary_prompt
from ..shared.prometheus_client import (
    # New simplified time series functions (optimized for agent use)
    prometheus_get_timeseries, prometheus_get_node_timeseries, prometheus_get_service_topology
)
import logging

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if not load_dotenv(dotenv_path=dotenv_path, override=True):
    raise RuntimeError(f"Failed to load .env from path: {dotenv_path}")

logger = logging.getLogger(__name__)

class KubernetesAgent:
    """
    Main Kubernetes agent with a simple loop-based approach.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            raise ValueError("config is required")
        
        self.config = config.copy()
        
        # Add reasoning summary config option (defaults to True for better explainability)
        if "show_reasoning" not in self.config:
            self.config["show_reasoning"] = True
        
        # New: include reasoning summaries in context fed back to LLM (now enabled by default)
        if "reasoning_in_context" not in self.config:
            self.config["reasoning_in_context"] = True
        
        # Load API key directly from environment
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable must be set. "
                "Please set it in your .env file or export it in your shell."
            )
        
        self.mcp_client = None
        self.openai_client = None
        self.is_initialized = False
        
        # Planning state
        self.current_plan = None
        self.plan_history = []
        self.current_step_index = 0  # Track which step we're executing
        
        # Simple redundancy prevention - track recent function calls
        self.recent_calls = {}  # {function_signature: timestamp}
        self.call_freshness_seconds = 30  # Skip identical calls within 30 seconds

    async def _retry_openai_call(self, api_call_func, max_retries: int = 5, base_delay: float = 1.0):
        """
        Wrapper for OpenAI API calls with exponential backoff retry logic for rate limits.
        
        Args:
            api_call_func: Async function that makes the OpenAI API call
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            
        Returns:
            Response from OpenAI API
            
        Raises:
            The original exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await api_call_func()
            
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Check if this is a rate limit error
                is_rate_limit = (
                    "rate limit" in error_str.lower() or
                    "rate_limit_exceeded" in error_str or
                    "429" in error_str
                )
                
                if not is_rate_limit or attempt == max_retries:
                    # Not a rate limit error or final attempt - re-raise
                    raise e
                
                # Calculate delay with exponential backoff and jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                
                logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay:.1f}s: {error_str}")
                print(f"⏳ Rate limit reached, retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries + 1})")
                
                await asyncio.sleep(delay)
        
        # This should never be reached, but just in case
        raise last_exception
    
    async def initialize(self):
        """Initialize the Kubernetes Agent with all required clients."""
        print("🔧 Initializing Kubernetes Agent...")
        print(f"   📋 Agent Config: max_rounds={self.config['max_rounds']}, timeout={self.config['agent_timeout']}s")
        
        # Initialize MCP client with the required server command
        # The server command should point to the MCP server for Kubernetes
        server_command = ["node", "./mcp-server-kubernetes/dist/index.js"]
        self.mcp_client = MCPClient(server_command)
        await self.mcp_client.start()
        await self.mcp_client.initialize()
        print("   ✅ MCP Kubernetes client ready")
        
        # Initialize OpenAI client with API key from environment
        self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)
        print("   ✅ OpenAI client ready")
        
        self.is_initialized = True
        print("✅ Agent initialization complete")
    
    async def call_mcp(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call MCP server with kubectl function.
        
        Args:
            function_name: Name of the kubectl function to call
            parameters: Parameters for the function
            
        Returns:
            Result from MCP server
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        try:
            result = await self.mcp_client.call_tool(function_name, parameters)
            return result
        except Exception as e:
            error_result = {"error": f"MCP call failed: {str(e)}"}
            print(f"❌ MCP Error: {str(e)}")
            return error_result
    
    async def call_prometheus_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Prometheus metrics function.
        
        Args:
            function_name: Name of the prometheus function to call
            parameters: Parameters for the function
            
        Returns:
            Result from Prometheus query
        """
        try:
            # Map function names to actual functions (simplified)
            function_map = {
                "prometheus_get_timeseries": prometheus_get_timeseries,
                "prometheus_get_node_timeseries": prometheus_get_node_timeseries,
                "prometheus_get_service_topology": prometheus_get_service_topology
            }
            
            func = function_map.get(function_name)
            if not func:
                return {"error": f"Unknown Prometheus function: {function_name}"}
            
            # Call the function with parameters
            result = func(**parameters)
            return result
            
        except Exception as e:
            error_result = {"error": f"Prometheus call failed: {str(e)}"}
            print(f"❌ Prometheus Error: {str(e)}")
            return error_result
    
    def get_current_plan_step(self) -> Optional[str]:
        """Get the current step from the active plan."""
        if not self.current_plan or not self.current_plan.get('steps'):
            return None
        
        steps = self.current_plan.get('steps', [])
        if self.current_step_index < len(steps):
            return steps[self.current_step_index]
        return None
    
    def reset_plan_progress(self):
        """Reset plan step tracking (useful when replanning)."""
        self.current_step_index = 0
        # Clear recent calls when starting new plan to allow fresh data collection
        self.recent_calls.clear()
    
    def is_recent_call(self, function_name: str, parameters: Dict[str, Any]) -> Optional[str]:
        """Check if this exact function call was made recently. Returns skip reason if should skip."""
        # Create signature for this function call
        param_str = json.dumps(parameters, sort_keys=True) if parameters else ""
        call_signature = f"{function_name}_{param_str}"
        
        # Check if we made this exact call recently
        if call_signature in self.recent_calls:
            age = time.time() - self.recent_calls[call_signature]
            if age < self.call_freshness_seconds:
                return f"identical call made {age:.1f}s ago"
        
        return None  # Don't skip
    
    def record_function_call(self, function_name: str, parameters: Dict[str, Any]):
        """Record that we made this function call."""
        param_str = json.dumps(parameters, sort_keys=True) if parameters else ""
        call_signature = f"{function_name}_{param_str}"
        self.recent_calls[call_signature] = time.time()
    
    def convert_node_function_to_generic(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert node management function calls to kubectl_generic format.
        
        Args:
            function_name: Name of the node function (kubectl_drain, kubectl_cordon, kubectl_uncordon)
            args: Arguments for the node function
            
        Returns:
            Dict with kubectl_generic compatible arguments
        """
        if function_name == "kubectl_drain":
            node_name = args["node_name"]
            
            # Build flags for drain command
            flags = {}
            
            # Add flags based on parameters
            if args.get("ignore_daemonsets", True):
                flags["ignore-daemonsets"] = True
            
            if args.get("delete_emptydir_data", False):
                flags["delete-emptydir-data"] = True
            
            if args.get("force", False):
                flags["force"] = True
            
            if args.get("disable_eviction", False):
                flags["disable-eviction"] = True
            
            # Handle grace period (default is 30)
            grace_period = args.get("grace_period", 30)
            if grace_period != 30:  # Only add if different from default
                flags["grace-period"] = grace_period
            
            # Handle timeout
            timeout = args.get("timeout", "0s")
            if timeout != "0s":  # Only add if different from default
                flags["timeout"] = timeout
            
            return {
                "command": "drain",
                "name": node_name,
                "flags": flags
            }
        
        elif function_name == "kubectl_cordon":
            node_name = args["node_name"]
            return {
                "command": "cordon",
                "name": node_name
            }
        
        elif function_name == "kubectl_uncordon":
            node_name = args["node_name"]
            return {
                "command": "uncordon", 
                "name": node_name
            }
        
        else:
            raise ValueError(f"Unknown node function: {function_name}")
    
    async def ask_llm_step(self, context: List[str]) -> Dict[str, Any]:
        """
        Ask the LLM for the next step based on current context.
        
        Args:
            context: List of context strings from previous rounds
            
        Returns:
            LLM response with potential function call
        """
        if not self.is_initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Build the context message
        context_text = "\n".join(context)
        
        # Add plan guidance if we have an active plan
        plan_guidance = ""
        if self.current_plan and self.current_plan.get('status') == 'active':
            current_step = self.get_current_plan_step()
            if current_step:
                steps = self.current_plan.get('steps', [])
                plan_guidance = f"\n\nCURRENT PLAN GUIDANCE:\nObjective: {self.current_plan.get('objective')}\nCurrent Step ({self.current_step_index + 1}/{len(steps)}): {current_step}\n"
            else:
                plan_guidance = f"\n\nPLAN STATUS: All planned steps completed. Objective: {self.current_plan.get('objective')}\n"
        
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": f"Based on the following context, what should you do next?\n\n{context_text}{plan_guidance}"}
        ]
        
        # Get all available functions from tool schemas
        functions = get_kubernetes_function_schemas()
        
        try:
            response = await self._retry_openai_call(
                lambda: self.openai_client.chat.completions.create(
                    model=self.config["openai_model"],
                    messages=messages,
                    functions=functions,
                    function_call="auto"
                )
            )
            
            message = response.choices[0].message
            
            result = {
                "content": message.content,
                "function_call": None
            }
            
            if message.function_call:
                result["function_call"] = {
                    "name": message.function_call.name,
                    "arguments": json.loads(message.function_call.arguments)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return {"error": f"OpenAI API error: {str(e)}"}
    
    async def handle_planning_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle planning and strategy functions.

        Args:
            function_name: Name of the planning function
            parameters: Parameters for the function

        Returns:
            Result of the planning operation
        """
        try:
            if function_name == "create_action_plan":
                plan = {
                    "objective": parameters.get("objective"),
                    "current_situation": parameters.get("current_situation"),
                    "steps": parameters.get("steps", []),
                    "expected_outcome": parameters.get("expected_outcome"),
                    "risks_considerations": parameters.get("risks_considerations", []),
                    "created_at": time.time(),
                    "status": "active"
                }

                self.current_plan = plan
                self.plan_history.append(plan)
                self.reset_plan_progress()  # Reset step tracking for new plan

                return {
                    "status": "success",
                    "message": "Action plan created successfully",
                    "plan": plan
                }

            elif function_name == "generate_operational_summary":
                # Extract problem_location - handle both new array format and old dict format
                problem_location_param = parameters.get("problem_location", [])
                problem_location_list = []
                
                # If it's already a list (new format), use it directly
                if isinstance(problem_location_param, list):
                    problem_location_list = problem_location_param
                # If it's a dict (old format), convert it
                elif isinstance(problem_location_param, dict):
                    # Convert old format to new format
                    for resource_type in ["deployment", "pod", "node", "service"]:
                        plural_key = f"{resource_type}s"
                        if plural_key in problem_location_param:
                            resources = problem_location_param[plural_key]
                            if isinstance(resources, list):
                                for name in resources:
                                    problem_location_list.append({
                                        "name": name,
                                        "type": resource_type
                                    })
                            elif isinstance(resources, str):
                                problem_location_list.append({
                                    "name": resources,
                                    "type": resource_type
                                })
                
                summary = {
                    "objective": parameters.get("objective"),
                    "actions_completed": parameters.get("actions_completed", []),
                    "results_achieved": parameters.get("results_achieved", []),
                    "status": parameters.get("status"),
                    "problem_location": problem_location_list,  # Now always a list
                    "success": parameters.get("success", False),
                    "timestamp": time.time(),
                    "plan_info": {
                        "plans_created": len(self.plan_history),
                        "final_plan_status": self.current_plan.get('status') if self.current_plan else "none"
                    }
                }

                # Mark this as operation completion
                if self.current_plan:
                    self.current_plan["status"] = "completed_with_summary"

                print("\n" + "="*60)
                print("📊 OPERATIONAL SUMMARY")
                print("="*60)
                print(f"🎯 Objective: {summary['objective']}")
                print(f"📋 Status: {summary['status']}")
                
                # Display success/failure prominently
                success_icon = "✅" if summary['success'] else "❌"
                success_text = "SUCCEEDED" if summary['success'] else "FAILED"
                print(f"🏆 Resolution: {success_icon} {success_text}")
                
                # Display problem location details if provided (new format)
                if problem_location_list:
                    print(f"\n📍 PROBLEM LOCATION:")
                    # Group by type for display
                    by_type = {}
                    for item in problem_location_list:
                        resource_type = item.get('type', 'unknown')
                        if resource_type not in by_type:
                            by_type[resource_type] = []
                        by_type[resource_type].append(item.get('name', 'unknown'))
                    
                    # Display grouped by type
                    type_emojis = {
                        'deployment': '🚀',
                        'service': '🔗',
                        'node': '🖥️',
                        'pod': '📦'
                    }
                    for resource_type, names in by_type.items():
                        emoji = type_emojis.get(resource_type, '📦')
                        names_str = ', '.join(names)
                        print(f"   {emoji} {resource_type.capitalize()}s: {names_str}")
                
                print(f"\n✅ Actions Completed ({len(summary['actions_completed'])}):")
                for i, action in enumerate(summary['actions_completed'], 1):
                    print(f"   {i}. {action}")
                print(f"\n🎯 Results Achieved ({len(summary['results_achieved'])}):")
                for i, result in enumerate(summary['results_achieved'], 1):
                    print(f"   {i}. {result}")
                print(f"\n📈 Plans Created: {summary['plan_info']['plans_created']}")
                print(f"🏁 Final Plan Status: {summary['plan_info']['final_plan_status']}")
                print("="*60)

                return {
                    "status": "success",
                    "message": "Operational summary generated",
                    "summary": summary,
                    "operation_complete": True
                }

            else:
                return {"error": f"Unknown planning function: {function_name}"}

        except Exception as e:
            error_result = {"error": f"Planning function failed: {str(e)}"}
            return error_result
    
    async def agent_loop(self, intent: str, snapshot: Dict[str, Any] = None) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Main agent loop based on the user's template.
        
        Args:
            intent: What the agent should accomplish
            snapshot: Initial state information (optional)
            
        Returns:
            Tuple of (actions_taken, operational_summary)
        """
        if not self.is_initialized:
            await self.initialize()
        
        snapshot = snapshot or {}
        context = [
            f"Intent: {intent}",
            f"Snapshot: {json.dumps(snapshot, indent=2)}"
        ]
        
        actions_taken = []
        
        print(f"🤖 AGENT STARTED")
        print(f"   Intent: {intent}")
        print(f"   Max rounds: {self.config['max_rounds']}")
        print(f"   Context snapshot keys: {list(snapshot.keys()) if snapshot else 'None'}")
        
        agent_success = False
        agent_error = None
        interrupted = False
        final_summary = None
        
        try:
            for round_num in range(self.config['max_rounds']):
                print(f"\n🔄 Round {round_num + 1}/{self.config['max_rounds']}")
                
                llm_msg = await self.ask_llm_step(context)
                
                if llm_msg.get("error"):
                    print(f"❌ LLM Error: {llm_msg['error']}")
                    break
                
                if llm_msg.get("function_call"):
                    func_name = llm_msg["function_call"]["name"]
                    args = llm_msg["function_call"]["arguments"]
                    
                    # Check for redundant data collection calls (skip planning functions)
                    if func_name not in ["create_action_plan", "generate_operational_summary"]:
                        skip_reason = self.is_recent_call(func_name, args)
                        if skip_reason:
                            print(f"⏭️  Skipping {func_name}: {skip_reason}")
                            context.append(f"Skipped redundant {func_name} call: {skip_reason}")
                            continue
                    
                    print(f"⚡ Executing: {func_name}")
                    if args:
                        print(f"   Parameters: {json.dumps(args, indent=2)}")
                    
                    result = None
                    tool_error = None
                    
                    # Handle planning functions
                    if func_name in ["create_action_plan", "generate_operational_summary"]:
                        result = await self.handle_planning_function(func_name, args)
                        action = f"Executed {func_name}"
                        context.append(action)
                        context.append(f"Result: {json.dumps(result, indent=2)}")
                        actions_taken.append({
                            "type": "planning",
                            "function": func_name,
                            "parameters": args
                        })
                        print(f"✅ Planning function completed")
                        
                        # Capture final summary for logging
                        if func_name == "generate_operational_summary":
                            final_summary = result
                            agent_success = result.get("summary", {}).get("success", result.get("success", False))
                        
                        # ALWAYS exit after operational summary - no conditions needed
                        if func_name == "generate_operational_summary":
                            print(f"🏁 Operation completed with summary - agent exiting")
                            break
                    
                    # Handle kubectl functions
                    elif func_name in [
                        "kubectl_apply", "kubectl_get", "kubectl_delete", 
                        "kubectl_list", "kubectl_scale", "kubectl_patch",
                        "kubectl_describe", "kubectl_logs", "kubectl_rollout"
                    ]:
                        result = await self.call_mcp(func_name, args)
                        action = f"Executed {func_name}: {args}"
                        context.append(action)
                        context.append(f"Result: {json.dumps(result, indent=2)}")
                        actions_taken.append({
                            "type": "mcp_call",
                            "function": func_name,
                            "parameters": args
                        })
                        print(f"✅ MCP call completed")
                        
                        # Record this function call to prevent redundancy
                        self.record_function_call(func_name, args)
                        
                        # Show reasoning summary
                        await self.display_reasoning_if_enabled(context, func_name, result)
                    
                    # Handle node management functions using kubectl_generic
                    elif func_name in ["kubectl_drain", "kubectl_cordon", "kubectl_uncordon"]:
                        # Convert the node management function to kubectl_generic call
                        generic_args = self.convert_node_function_to_generic(func_name, args)
                        result = await self.call_mcp("kubectl_generic", generic_args)
                        action = f"Executed {func_name}: {args}"
                        context.append(action)
                        context.append(f"Result: {json.dumps(result, indent=2)}")
                        actions_taken.append({
                            "type": "mcp_call",
                            "function": func_name,
                            "parameters": args
                        })
                        print(f"✅ Node management call completed")
                        
                        # Record this function call to prevent redundancy
                        self.record_function_call(func_name, args)
                        
                        # Show reasoning summary
                        await self.display_reasoning_if_enabled(context, func_name, result)
                    
                    # Handle prometheus functions (simplified)
                    elif func_name in [
                        "prometheus_get_timeseries",
                        "prometheus_get_node_timeseries",
                        "prometheus_get_service_topology"
                    ]:
                        result = await self.call_prometheus_function(func_name, args)
                        action = f"Executed {func_name}: {args}"
                        context.append(action)
                        context.append(f"Result: {json.dumps(result, indent=2)}")
                        actions_taken.append({
                            "type": "prometheus_call",
                            "function": func_name,
                            "parameters": args
                        })
                        print(f"✅ Prometheus call completed")
                        
                        # Record this function call to prevent redundancy
                        self.record_function_call(func_name, args)
                        
                        # Show reasoning summary
                        await self.display_reasoning_if_enabled(context, func_name, result)
                    
                    elif func_name == "sleep_seconds":
                        duration = args["duration"]
                        print(f"💤 Sleeping for {duration} seconds...")
                        await asyncio.sleep(duration)
                        action = f"Slept {duration} seconds"
                        context.append(action)
                        actions_taken.append({
                            "type": "sleep",
                            "duration": duration
                        })
                        print(f"✅ Sleep completed")
                        
                        # Record this function call to prevent redundancy
                        self.record_function_call(func_name, args)
                        
                        # Show reasoning summary
                        result = {"duration": duration, "status": "completed"}
                        await self.display_reasoning_if_enabled(context, func_name, result)
                    
                    else:
                        print(f"⚠️ Unknown function: {func_name}")
                        result = {"error": f"Unknown function: {func_name}"}
                        tool_error = f"Unknown function: {func_name}"
                
                else:
                    completion_msg = llm_msg.get('content', '').strip()
                    if completion_msg:
                        print(f"💭 Agent says: {completion_msg}")
                    
                    # Check if this looks like a completion message or if we should continue
                    # Agent should only stop if it explicitly indicates completion
                    completion_indicators = [
                        "operation complete", "objective achieved", "task completed",
                        "summary provided", "mission accomplished", "finished successfully"
                    ]
                    
                    is_completion = any(indicator in completion_msg.lower() for indicator in completion_indicators)
                    
                    # If this looks like completion but no summary was generated, warn and continue
                    if is_completion:
                        # Check if we had a summary in recent actions
                        recent_summaries = [
                            action for action in actions_taken 
                            if isinstance(action, dict) and action.get("function") == "generate_operational_summary"
                        ]
                        if not recent_summaries:
                            print(f"⚠️ Agent indicated completion but no operational summary provided. Requesting summary...")
                            context.append(f"SYSTEM: Agent indicated completion with message: '{completion_msg}' but no operational summary was generated. You must provide a generate_operational_summary before completion.")
                            continue
                        else:
                            print(f"🏁 Agent completed with operational summary")
                            break
                    else:
                        # Agent provided content but didn't indicate completion - this might be premature
                        print(f"⚠️ Agent provided content without function call or completion indicator")
                        print(f"   Consider whether objective is truly complete or if more actions are needed")
                        
                        # Add guidance to context about completion requirements
                        context.append(f"Agent provided message: '{completion_msg}'. If objective is complete, use generate_operational_summary. If not complete, continue with planned actions.")
                        
                        # Only break if we're at the last round, otherwise continue
                        if round_num == self.config['max_rounds'] - 1:
                            print(f"🚨 Maximum rounds reached without proper completion. Requesting emergency summary...")
                            context.append("SYSTEM: Maximum rounds reached. You MUST generate an operational summary now using generate_operational_summary function.")
                        else:
                            continue
            
            agent_success = True  # If we got here without exception, agent completed normally
            
        except KeyboardInterrupt:
            interrupted = True
            agent_error = "Agent execution interrupted by user"
            print(f"\n🛑 Agent execution interrupted by user")
        except Exception as e:
            agent_error = str(e)
            print(f"\n❌ Agent execution failed: {e}")
            logger.exception("Agent execution error")
        
        print(f"\n🎯 AGENT FINISHED")
        print(f"   Actions taken: {len(actions_taken)}")
        if self.current_plan:
            print(f"   Final plan status: {self.current_plan.get('status', 'unknown')}")
        
        # Check if operation completed properly with summary
        summary_actions = [
            action for action in actions_taken 
            if isinstance(action, dict) and action.get("function") == "generate_operational_summary"
        ]
        if summary_actions:
            print(f"   ✅ Operation completed with structured summary")
        else:
            print(f"   ⚠️ Operation finished without structured summary")
            
        return actions_taken, final_summary

    async def get_reasoning_summary(self, context: List[str], last_function: str, last_result: Dict[str, Any]) -> str:
        """
        Get a brief reasoning summary from the LLM after a tool call.
        
        Args:
            context: Current context from the agent loop
            last_function: Name of the function that was just executed
            last_result: Result from the last function call
            
        Returns:
            Reasoning summary string
        """
        if not self.is_initialized:
            return "Agent not initialized"
        
        try:
            # Build reasoning prompt using the prompts module
            context_text = "\n".join(context[-5:])  # Last 5 context items to avoid too much text
            last_result_preview = json.dumps(last_result, indent=2)[:500] + "..."
            
            reasoning_prompt = get_reasoning_summary_prompt(
                context_text=context_text,
                last_function=last_function,
                last_result_preview=last_result_preview
            )

            messages = [
                {"role": "user", "content": reasoning_prompt}
            ]
            
            response = await self._retry_openai_call(
                lambda: self.openai_client.chat.completions.create(
                    model=self.config["openai_model"],
                    messages=messages,
                    max_tokens=300,  # Increased for detailed reflective analysis
                    temperature=0.1  # Keep it factual
                )
            )
            
            reasoning = response.choices[0].message.content.strip()
            return reasoning
            
        except Exception as e:
            logger.error(f"Error getting reasoning summary: {e}")
            return f"Unable to generate reasoning summary: {str(e)}"

    async def display_reasoning_if_enabled(self, context: List[str], function_name: str, result: Dict[str, Any]):
        """Display reasoning summary and add to context for reflection."""
        if not self.config.get("show_reasoning", True):
            return
            
        try:
            reasoning = await self.get_reasoning_summary(context, function_name, result)
            print(f"\n🧠 CRITICAL ANALYSIS: {reasoning}")

            # Always feed reasoning back into context when reasoning is enabled - this is now the default
            if self.config.get("reasoning_in_context", True):
                context.append(f"CRITICAL_ANALYSIS: {reasoning}")
                print(f"   📝 Added reasoning to context for next LLM call")
        except Exception as e:
            logger.error(f"Error displaying reasoning: {e}")

    async def cleanup(self):
        """Clean up resources."""
        print("🧹 Cleaning up agent...")
        if self.mcp_client:
            await self.mcp_client.stop()
        self.is_initialized = False
        print("✅ Agent cleanup complete")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()            