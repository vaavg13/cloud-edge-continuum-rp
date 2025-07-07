"""
Configuration Schema for Drift Monitor
Defines the structure and validation for monitoring configurations.
"""

from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator

from ..shared.types import MetricType, ComparisonOperator

class ThresholdConfig(BaseModel):
    """Configuration for a single metric threshold."""
    metric_type: MetricType = Field(..., description="Type of metric to monitor")
    threshold_value: float = Field(..., description="Threshold value to compare against")
    operator: ComparisonOperator = Field(..., description="Comparison operator")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'ms', 'cores', 'MB')")
    consecutive_violations: int = Field(1, description="Number of consecutive violations before triggering action")
    description: Optional[str] = Field(None, description="Human-readable description of this threshold")



class DriftMonitorConfig(BaseModel):
    """Configuration for a single monitoring loop - pure monitoring only."""
    version: str = Field("1.0", description="Configuration schema version")
    prometheus_url: str = Field("http://localhost:9090", description="Prometheus server URL")
    
    # Single monitoring loop configuration
    loop_id: str = Field(..., description="Unique identifier for this monitoring loop")
    namespace: str = Field(..., description="Kubernetes namespace to monitor (required)")
    deployment_name: Optional[str] = Field(None, description="Specific deployment name to monitor (optional)")
    thresholds: List[ThresholdConfig] = Field(..., description="List of thresholds to monitor")
    check_interval_seconds: int = Field(60, description="Interval between metric checks in seconds")
    enabled: bool = Field(True, description="Whether this monitoring loop is enabled")
    description: Optional[str] = Field(None, description="Human-readable description of this loop")

    @field_validator('loop_id')
    def validate_loop_id(cls, v):
        """Validate loop_id follows naming conventions."""
        if not v.replace('-', '').replace('.', '').isalnum():
            raise ValueError('loop_id can only contain alphanumeric characters, hyphens, and dots')
        return v

    @field_validator('namespace')
    def validate_namespace(cls, v):
        """Validate namespace follows Kubernetes naming conventions."""
        if not v.replace('-', '').replace('.', '').isalnum():
            raise ValueError('namespace can only contain alphanumeric characters, hyphens, and dots')
        return v 