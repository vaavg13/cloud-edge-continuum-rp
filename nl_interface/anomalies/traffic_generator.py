import asyncio
import time
import httpx
import logging
import statistics
from typing import Dict, List

logger = logging.getLogger(__name__)

class TrafficGenerator:
    """Generates continuous HTTP traffic to test endpoints."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.is_running = False
        self.tasks = []
        self.current_phase_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": []
        }
        
    def _calculate_p95_latency(self, response_times: List[float]) -> float:
        """Calculate P95 latency from response times."""
        if not response_times:
            return 0.0
        if len(response_times) == 1:
            return response_times[0]
        
        try:
            return statistics.quantile(response_times, 0.95)
        except AttributeError:
            # Fallback for older Python versions
            sorted_times = sorted(response_times)
            index = int(len(sorted_times) * 0.95)
            if index >= len(sorted_times):
                index = len(sorted_times) - 1
            return sorted_times[index]
        
    async def send_request(self, client: httpx.AsyncClient, url: str):
        """Send a single HTTP request and collect metrics."""
        start_time = time.time()
        try:
            response = await client.get(url, timeout=self.config["request_timeout"])
            response_time = time.time() - start_time
            
            self.current_phase_metrics["total_requests"] += 1
            if response.status_code == 200:
                self.current_phase_metrics["successful_requests"] += 1
            else:
                self.current_phase_metrics["failed_requests"] += 1
            
            if self.config["collect_metrics"]:
                self.current_phase_metrics["response_times"].append(response_time)
                
        except Exception as e:
            response_time = time.time() - start_time
            self.current_phase_metrics["total_requests"] += 1
            self.current_phase_metrics["failed_requests"] += 1
            
            if self.config["collect_metrics"]:
                self.current_phase_metrics["response_times"].append(response_time)
    
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
            
        self.is_running = True
        
        # Start a worker for each endpoint
        for endpoint in self.config["endpoints"]:
            task = asyncio.create_task(self.traffic_worker(endpoint))
            self.tasks.append(task)
    
    async def stop_traffic(self):
        """Stop all traffic generation."""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
    
    def get_phase_metrics(self) -> Dict:
        """Get metrics for the current phase and reset for next phase."""
        if self.current_phase_metrics["total_requests"] == 0:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate_percent": 0,
                "p95_latency_seconds": 0,
                "max_latency_seconds": 0
            }
        
        # Calculate metrics
        success_rate = (self.current_phase_metrics["successful_requests"] / self.current_phase_metrics["total_requests"]) * 100
        p95_latency = self._calculate_p95_latency(self.current_phase_metrics["response_times"])
        max_latency = max(self.current_phase_metrics["response_times"]) if self.current_phase_metrics["response_times"] else 0
        
        metrics = {
            "total_requests": self.current_phase_metrics["total_requests"],
            "successful_requests": self.current_phase_metrics["successful_requests"],
            "failed_requests": self.current_phase_metrics["failed_requests"],
            "success_rate_percent": round(success_rate, 2),
            "p95_latency_seconds": round(p95_latency, 3),
            "max_latency_seconds": round(max_latency, 3)
        }
        
        # Reset for next phase
        self.current_phase_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": []
        }
        
        return metrics 