#!/usr/bin/env python3
"""
Test script to verify workmodel generation without calling OpenAI.
Uses mock service data to test the JSON formatting.
"""

import json
from workmodel_prompt_template import format_service_json

def create_test_config():
    """Create test configuration."""
    return {
        "num_services": 3,
        "service_prefix": "s",
        "edge_sites_list": ["edge-site-1", "edge-site-2"],
        "cloud_site_name": "cloud",
        "app_profile": "iot_data_processing",
        "ingress_service_name": "s0",
        "default_request_method": "rest",
        "default_image": "msvcbench/microservice_v6-screen:1.0",
        "default_namespace": "default",
        "default_api_path": "/api/v1"
    }

def create_mock_service_data():
    """Create mock service data to test formatting."""
    return [
        {
            "service_name": "s0",
            "function_id": "f0",
            "external_services": [
                {
                    "seq_len": 100,
                    "services": ["s1"],
                    "probabilities": {"s1": 0.7}
                },
                {
                    "seq_len": 100,
                    "services": ["s2"],
                    "probabilities": {"s2": 0.3}
                }
            ],
            "cpu_stress_run": True,
            "cpu_range_complexity": [15, 30],
            "cpu_thread_pool_size": 1,
            "cpu_trials": 1,
            "memory_stress_run": False,
            "memory_size": 0,
            "memory_io": 0,
            "disk_stress_run": False,
            "disk_tmp_file_name": "",
            "disk_write_block_count": 0,
            "disk_write_block_size": 0,
            "sleep_stress_run": False,
            "sleep_time": 0,
            "mean_response_size": 30,
            "request_method": "rest",
            "workers": 4,
            "threads": 16,
            "deployments": [
                {
                    "deployment_name_suffix": "edge-site-1",
                    "node_affinity_zone": "edge-site-1",
                    "cpu_requests": "100m",
                    "memory_requests": "128Mi",
                    "cpu_limits": "200m",
                    "memory_limits": "256Mi",
                    "autoscaling_enabled": True,
                    "autoscaling_min": 2,
                    "autoscaling_max": 5,
                    "autoscaling_metric": "cpu",
                    "autoscaling_target": 60
                },
                {
                    "deployment_name_suffix": "edge-site-2",
                    "node_affinity_zone": "edge-site-2",
                    "cpu_requests": "100m",
                    "memory_requests": "128Mi",
                    "cpu_limits": "200m",
                    "memory_limits": "256Mi",
                    "autoscaling_enabled": True,
                    "autoscaling_min": 1,
                    "autoscaling_max": 5,
                    "autoscaling_metric": "cpu",
                    "autoscaling_target": 60
                }
            ]
        },
        {
            "service_name": "s1",
            "function_id": "f1",
            "external_services": [
                {
                    "seq_len": 1,
                    "services": []
                }
            ],
            "cpu_stress_run": True,
            "cpu_range_complexity": [20, 40],
            "cpu_thread_pool_size": 2,
            "cpu_trials": 1,
            "memory_stress_run": True,
            "memory_size": 5000,
            "memory_io": 250,
            "disk_stress_run": False,
            "disk_tmp_file_name": "",
            "disk_write_block_count": 0,
            "disk_write_block_size": 0,
            "sleep_stress_run": False,
            "sleep_time": 0,
            "mean_response_size": 40,
            "request_method": "rest",
            "workers": 4,
            "threads": 16,
            "deployments": [
                {
                    "deployment_name_suffix": "edge-site-1",
                    "node_affinity_zone": "edge-site-1",
                    "cpu_requests": "150m",
                    "memory_requests": "160Mi",
                    "cpu_limits": "300m",
                    "memory_limits": "256Mi",
                    "autoscaling_enabled": True,
                    "autoscaling_min": 1,
                    "autoscaling_max": 5,
                    "autoscaling_metric": "cpu",
                    "autoscaling_target": 60
                }
            ]
        },
        {
            "service_name": "s2",
            "function_id": "f2",
            "external_services": [
                {
                    "seq_len": 1,
                    "services": []
                }
            ],
            "cpu_stress_run": True,
            "cpu_range_complexity": [25, 45],
            "cpu_thread_pool_size": 2,
            "cpu_trials": 1,
            "memory_stress_run": True,
            "memory_size": 6000,
            "memory_io": 300,
            "disk_stress_run": False,
            "disk_tmp_file_name": "",
            "disk_write_block_count": 0,
            "disk_write_block_size": 0,
            "sleep_stress_run": False,
            "sleep_time": 0,
            "mean_response_size": 50,
            "request_method": "rest",
            "workers": 4,
            "threads": 16,
            "deployments": [
                {
                    "deployment_name_suffix": "cloud",
                    "node_affinity_zone": "cloud",
                    "cpu_requests": "150m",
                    "memory_requests": "160Mi",
                    "cpu_limits": "300m",
                    "memory_limits": "256Mi",
                    "autoscaling_enabled": True,
                    "autoscaling_min": 1,
                    "autoscaling_max": 5,
                    "autoscaling_metric": "cpu",
                    "autoscaling_target": 60
                }
            ]
        }
    ]

def test_workmodel_generation():
    """Test the workmodel JSON generation."""
    print("Testing workmodel JSON generation...")
    
    config = create_test_config()
    mock_services = create_mock_service_data()
    
    # Generate JSON for each service
    all_services_json = []
    for service_params in mock_services:
        service_json = format_service_json(service_params, config)
        all_services_json.append(service_json)
    
    # Combine into final JSON
    full_json_string = "{\n" + ",\n".join(all_services_json) + "\n}"
    
    # Validate JSON
    try:
        workmodel_dict = json.loads(full_json_string)
        print("✅ JSON is valid!")
        
        # Verify structure
        assert "s0" in workmodel_dict, "Missing s0 service"
        assert "s1" in workmodel_dict, "Missing s1 service"
        assert "s2" in workmodel_dict, "Missing s2 service"
        
        # Check s0 probabilities
        s0_external = workmodel_dict["s0"]["external_services"]
        assert len(s0_external) == 2, f"Expected 2 external services for s0, got {len(s0_external)}"
        
        # Find the service that calls s1
        s1_call = next((ext for ext in s0_external if "s1" in ext.get("services", [])), None)
        assert s1_call is not None, "s0 should call s1"
        assert "propabilities" in s1_call, "Missing probabilities for s1 call"
        assert s1_call["propabilities"]["s1"] == 0.7, f"Expected s1 probability 0.7, got {s1_call['propabilities']['s1']}"
        
        # Check inferred fields
        assert workmodel_dict["s0"]["image"] == "msvcbench/microservice_v6-screen:1.0", "Image not inferred correctly"
        assert workmodel_dict["s0"]["namespace"] == "default", "Namespace not inferred correctly"
        assert workmodel_dict["s0"]["path"] == "/api/v1", "Path not inferred correctly"
        
        # Check deployments
        assert len(workmodel_dict["s0"]["deployments"]) == 2, "s0 should have 2 deployments"
        assert len(workmodel_dict["s1"]["deployments"]) == 1, "s1 should have 1 deployment"
        assert len(workmodel_dict["s2"]["deployments"]) == 1, "s2 should have 1 deployment"
        
        print("✅ All structure validations passed!")
        
        # Pretty print the result
        print("\n--- Generated Workmodel JSON ---")
        print(json.dumps(workmodel_dict, indent=2))
        
        # Save to file for inspection
        with open("test_workmodel_output.json", "w") as f:
            json.dump(workmodel_dict, f, indent=2)
        print(f"\n✅ Saved test output to: test_workmodel_output.json")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON validation failed: {e}")
        print("Raw output:")
        print(full_json_string)
        return False
    except AssertionError as e:
        print(f"❌ Structure validation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_workmodel_generation()
    if success:
        print("\n🎉 All tests passed! The workmodel generation is working correctly.")
    else:
        print("\n❌ Tests failed. Please check the implementation.") 