#!/usr/bin/env python3
"""
Traffic Generator Module
Generates HTTP traffic and collects latency metrics across different test phases.
"""

import asyncio
import time
import httpx
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class TrafficGenerator:
    """Generates continuous HTTP traffic to test endpoints."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.is_running = False
        self.tasks = []
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "errors": [],
            "phase_metrics": {
                "baseline": {"max_latency": 0, "avg_latency": 0, "request_count": 0},
                "chaos": {"max_latency": 0, "avg_latency": 0, "request_count": 0},
                "recovery": {"max_latency": 0, "avg_latency": 0, "request_count": 0}
            }
        }
        self.current_phase = "baseline"
        
    async def send_request(self, client: httpx.AsyncClient, url: str):
        """Send a single HTTP request and collect metrics."""
        start_time = time.time()
        try:
            response = await client.get(url, timeout=self.config["request_timeout"])
            response_time = time.time() - start_time
            
            self.metrics["total_requests"] += 1
            if response.status_code == 200:
                self.metrics["successful_requests"] += 1
            else:
                self.metrics["failed_requests"] += 1
                self.metrics["errors"].append(f"HTTP {response.status_code}")
            
            if self.config["collect_metrics"]:
                self.metrics["response_times"].append(response_time)
                
                # Track phase-specific metrics
                phase_data = self.metrics["phase_metrics"][self.current_phase]
                phase_data["request_count"] += 1
                phase_data["max_latency"] = max(phase_data["max_latency"], response_time)
                
                # Calculate running average for phase
                if phase_data["request_count"] == 1:
                    phase_data["avg_latency"] = response_time
                else:
                    phase_data["avg_latency"] = (
                        (phase_data["avg_latency"] * (phase_data["request_count"] - 1) + response_time) 
                        / phase_data["request_count"]
                    )
            
            # Print status occasionally for visibility
            if self.metrics["total_requests"] % 50 == 0:
                success_rate = (self.metrics["successful_requests"] / self.metrics["total_requests"]) * 100
                avg_response_time = sum(self.metrics["response_times"]) / len(self.metrics["response_times"]) if self.metrics["response_times"] else 0
                phase_max = self.metrics["phase_metrics"][self.current_phase]["max_latency"]
                print(f"   Traffic ({self.current_phase}): {self.metrics['total_requests']} requests, {success_rate:.1f}% success, {avg_response_time:.2f}s avg, {phase_max:.2f}s max")
                
        except Exception as e:
            self.metrics["total_requests"] += 1
            self.metrics["failed_requests"] += 1
            self.metrics["errors"].append(str(e))
    
    async def traffic_worker(self, endpoint: str):
        """Worker that generates continuous traffic to an endpoint."""
        async with httpx.AsyncClient() as client:
            while self.is_running:
                await self.send_request(client, endpoint)
                # Wait based on requests_per_second config
                await asyncio.sleep(1.0 / self.config["requests_per_second"])
    
    async def start_traffic(self):
        """Start generating traffic to all configured endpoints."""
        if self.is_running:
            return
            
        print(f"🚦 Starting traffic generation...")
        print(f"   Endpoints: {len(self.config['endpoints'])}")
        print(f"   Rate: {self.config['requests_per_second']} req/s per endpoint")
        
        self.is_running = True
        
        # Start a worker for each endpoint
        for endpoint in self.config["endpoints"]:
            task = asyncio.create_task(self.traffic_worker(endpoint))
            self.tasks.append(task)
        
        print(f"✅ Traffic generation started with {len(self.tasks)} workers")
    
    async def stop_traffic(self):
        """Stop all traffic generation."""
        if not self.is_running:
            return
            
        print(f"🛑 Stopping traffic generation...")
        self.is_running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        print(f"✅ Traffic generation stopped")
    
    def set_phase(self, phase: str):
        """Set the current measurement phase (baseline, chaos, recovery)."""
        if phase in self.metrics["phase_metrics"]:
            self.current_phase = phase
            print(f"📊 Traffic measurement phase: {phase}")
    
    def reset_metrics(self):
        """Reset all metrics and phase data."""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "errors": [],
            "phase_metrics": {
                "baseline": {"max_latency": 0, "avg_latency": 0, "request_count": 0},
                "chaos": {"max_latency": 0, "avg_latency": 0, "request_count": 0},
                "recovery": {"max_latency": 0, "avg_latency": 0, "request_count": 0}
            }
        }
        self.current_phase = "baseline"
    
    def get_phase_summary(self) -> Dict:
        """Get a summary of latency by phase."""
        return {
            phase: {
                "max_latency_seconds": round(data["max_latency"], 3),
                "avg_latency_seconds": round(data["avg_latency"], 3),
                "request_count": data["request_count"]
            }
            for phase, data in self.metrics["phase_metrics"].items()
            if data["request_count"] > 0
        }
    
    def get_metrics_summary(self) -> Dict:
        """Get a summary of traffic metrics."""
        if not self.metrics["response_times"]:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0
        else:
            avg_response_time = sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
            min_response_time = min(self.metrics["response_times"])
            max_response_time = max(self.metrics["response_times"])
        
        success_rate = (self.metrics["successful_requests"] / self.metrics["total_requests"]) * 100 if self.metrics["total_requests"] > 0 else 0
        
        return {
            "total_requests": self.metrics["total_requests"],
            "successful_requests": self.metrics["successful_requests"],
            "failed_requests": self.metrics["failed_requests"],
            "success_rate_percent": round(success_rate, 2),
            "avg_response_time_seconds": round(avg_response_time, 3),
            "min_response_time_seconds": round(min_response_time, 3),
            "max_response_time_seconds": round(max_response_time, 3),
            "unique_errors": len(set(self.metrics["errors"])),
            "total_errors": len(self.metrics["errors"])
        }
    
    def print_comprehensive_summary(self):
        """Print comprehensive traffic analysis including phase comparisons."""
        metrics = self.get_metrics_summary()
        phase_summary = self.get_phase_summary()
        
        print(f"\n📊 OVERALL TRAFFIC SUMMARY")
        print("=" * 50)
        print(f"Total Requests: {metrics['total_requests']}")
        print(f"Successful: {metrics['successful_requests']}")
        print(f"Failed: {metrics['failed_requests']}")
        print(f"Success Rate: {metrics['success_rate_percent']}%")
        print(f"Overall Avg Response Time: {metrics['avg_response_time_seconds']}s")
        print(f"Overall Max Response Time: {metrics['max_response_time_seconds']}s")
        print("=" * 50)
        
        print(f"\n📈 PHASE-SPECIFIC LATENCY ANALYSIS")
        print("=" * 50)
        for phase, data in phase_summary.items():
            print(f"{phase.upper()}:")
            print(f"  Max Latency: {data['max_latency_seconds']}s")
            print(f"  Avg Latency: {data['avg_latency_seconds']}s")
            print(f"  Requests: {data['request_count']}")
        print("=" * 50)
        
        # Performance impact analysis
        if "baseline" in phase_summary and "chaos" in phase_summary:
            baseline_max = phase_summary["baseline"]["max_latency_seconds"]
            chaos_max = phase_summary["chaos"]["max_latency_seconds"]
            impact_ratio = chaos_max / baseline_max if baseline_max > 0 else float('inf')
            print(f"\n🎯 PERFORMANCE IMPACT ANALYSIS")
            print(f"Baseline Max Latency: {baseline_max}s")
            print(f"Chaos Max Latency: {chaos_max}s")
            print(f"Performance Degradation: {impact_ratio:.2f}x worse")
            
            if "recovery" in phase_summary:
                recovery_max = phase_summary["recovery"]["max_latency_seconds"]
                recovery_ratio = recovery_max / baseline_max if baseline_max > 0 else float('inf')
                print(f"Recovery Max Latency: {recovery_max}s")
                print(f"Recovery vs Baseline: {recovery_ratio:.2f}x")
                
                improvement = ((chaos_max - recovery_max) / chaos_max * 100) if chaos_max > 0 else 0
                print(f"Agent Improvement: {improvement:.1f}% reduction from chaos peak")
        print("=" * 50) 