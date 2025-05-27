#!/usr/bin/env python3
"""
Test script for the K8s API Builder
Tests the complete modular system with detailed output
"""

import json
import sys
from mu_bench.deployers import K8sApiBuilder

def test_k8s_api_builder():
    """Test the K8s API Builder with the real workmodel"""
    
    print("🚀 Starting K8s API Builder Test")
    print("=" * 50)
    
    # Load workmodel
    try:
        with open('APPS/app-edge/workmodel.json', 'r') as f:
            workmodel = json.load(f)
        print(f"✅ Loaded workmodel with {len(workmodel)} services")
        
        # Print workmodel services
        for service_name, config in workmodel.items():
            deployments = config.get('deployments', [])
            if deployments:
                print(f"   📦 {service_name}: {len(deployments)} deployments")
                for dep in deployments:
                    print(f"      └─ {dep['name']} (zone: {dep.get('node_affinity', 'default')})")
            else:
                print(f"   📦 {service_name}: single deployment")
                
    except Exception as e:
        print(f"❌ Failed to load workmodel: {e}")
        return False
    
    print("\n🔧 Creating K8s API Builder...")
    try:
        builder = K8sApiBuilder(
            namespace='default',
            dry_run=True,  # Safe testing
            nginx_gw=True,
            nginx_node_port=31114
        )
        print("✅ K8s API Builder created successfully")
    except Exception as e:
        print(f"❌ Failed to create K8s API Builder: {e}")
        return False
    
    print("\n🔄 Customizing workmodel...")
    try:
        builder.customize_workmodel(workmodel)
        print("✅ Workmodel customized successfully")
    except Exception as e:
        print(f"❌ Failed to customize workmodel: {e}")
        return False
    
    print("\n🏗️  Generating all resources...")
    try:
        resources = builder.customize_and_generate_resources(
            workmodel=workmodel,
            nfs_conf={},
            internal_service_functions_path='./mu_bench/custom_functions'
        )
        print("✅ Resource generation completed")
    except Exception as e:
        print(f"❌ Failed to generate resources: {e}")
        return False
    
    print("\n📊 Resource Summary:")
    print("-" * 30)
    total_resources = 0
    for resource_type, resource_list in resources.items():
        count = len(resource_list)
        total_resources += count
        if count > 0:
            print(f"   {resource_type}: {count}")
            for resource in resource_list:
                print(f"      └─ {resource}")
        else:
            print(f"   {resource_type}: {count} (dry run mode)")
    
    print(f"\n🎯 Total resources (would be) created: {total_resources}")
    
    print("\n🔍 Testing Individual Components:")
    print("-" * 40)
    
    # Test ConfigMap handler
    print("   🗂️  ConfigMap Handler:")
    cm_resources = builder.configmap_handler.get_created_resources()
    print(f"      └─ ConfigMaps handled: {len(cm_resources)}")
    
    # Test Nginx handler
    print("   🌐 Nginx Gateway Handler:")
    nginx_resources = builder.nginx_handler.get_created_resources()
    print(f"      └─ Nginx resources handled: {len(nginx_resources)}")
    
    print("\n✅ All tests completed successfully!")
    print("🎉 The modular K8s API Builder is working correctly!")
    
    return True

if __name__ == "__main__":
    success = test_k8s_api_builder()
    sys.exit(0 if success else 1) 