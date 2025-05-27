#!/usr/bin/env python3
"""
Deploy the MuBench app using the K8s API Builder
Creates namespace and deploys all resources for real
"""

import json
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from mu_bench.deployers import K8sApiBuilder

def ensure_namespace_exists(namespace_name: str) -> bool:
    """Ensure the namespace exists, create if it doesn't"""
    try:
        config.load_kube_config()
        core_v1 = client.CoreV1Api()
        
        # Check if namespace exists
        try:
            core_v1.read_namespace(name=namespace_name)
            print(f"✅ Namespace '{namespace_name}' already exists")
            return True
        except ApiException as e:
            if e.status == 404:
                # Namespace doesn't exist, create it
                namespace = client.V1Namespace(
                    metadata=client.V1ObjectMeta(name=namespace_name)
                )
                core_v1.create_namespace(body=namespace)
                print(f"✅ Created namespace '{namespace_name}'")
                return True
            else:
                print(f"❌ Error checking namespace: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Failed to ensure namespace: {e}")
        return False

def deploy_app():
    """Deploy the MuBench app using K8s API Builder"""
    
    print("🚀 Deploying MuBench App with K8s API Builder")
    print("=" * 60)
    
    # Configuration
    namespace = "mubench-test"
    
    # Load workmodel
    print("📋 Loading workmodel...")
    try:
        with open('APPS/app-edge/workmodel.json', 'r') as f:
            workmodel = json.load(f)
        print(f"✅ Loaded workmodel with {len(workmodel)} services")
        
        # Print workmodel summary
        for service_name, config in workmodel.items():
            deployments = config.get('deployments', [])
            if deployments:
                print(f"   📦 {service_name}: {len(deployments)} deployments")
                for dep in deployments:
                    zone = dep.get('node_affinity', 'default')
                    if '=' in zone:
                        zone = zone.split('=')[1]
                    print(f"      └─ {dep['name']} → {zone}")
            else:
                print(f"   📦 {service_name}: single deployment")
                
    except Exception as e:
        print(f"❌ Failed to load workmodel: {e}")
        return False
    
    # Ensure namespace exists
    print(f"\n🏗️  Ensuring namespace '{namespace}' exists...")
    if not ensure_namespace_exists(namespace):
        return False
    
    # Create K8s API Builder (NO dry run - real deployment)
    print("\n🔧 Creating K8s API Builder for real deployment...")
    try:
        builder = K8sApiBuilder(
            namespace=namespace,
            dry_run=False,  # REAL DEPLOYMENT
            nginx_gw=True,
            nginx_node_port=31114,
            image="msvcbench/microservice_v6-screen:1.0"
        )
        print("✅ K8s API Builder created successfully")
    except Exception as e:
        print(f"❌ Failed to create K8s API Builder: {e}")
        return False
    
    # Deploy all resources
    print("\n🚀 Deploying all resources...")
    try:
        builder.customize_workmodel(workmodel)
        resources = builder.customize_and_generate_resources(
            workmodel=workmodel,
            nfs_conf={},
            internal_service_functions_path='./mu_bench/custom_functions'
        )
        print("✅ Deployment completed successfully!")
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False
    
    # Show deployment summary
    print("\n📊 Deployment Summary:")
    print("-" * 40)
    total_resources = 0
    for resource_type, resource_list in resources.items():
        count = len(resource_list)
        total_resources += count
        if count > 0:
            print(f"   ✅ {resource_type}: {count}")
            for resource in resource_list:
                print(f"      └─ {resource}")
        else:
            print(f"   ⚪ {resource_type}: 0")
    
    print(f"\n🎯 Total resources created: {total_resources}")
    
    # Show access information
    print("\n🌐 Access Information:")
    print("-" * 30)
    print(f"   📍 Namespace: {namespace}")
    print(f"   🌐 Nginx Gateway: NodePort 31114")
    print(f"   🔍 Check pods: kubectl get pods -n {namespace}")
    print(f"   🔍 Check services: kubectl get svc -n {namespace}")
    print(f"   🔍 Check deployments: kubectl get deploy -n {namespace}")
    
    # Show cleanup command
    print("\n🧹 Cleanup (when done):")
    print(f"   kubectl delete namespace {namespace}")
    
    return True

def main():
    """Main function"""
    try:
        success = deploy_app()
        if success:
            print("\n🎉 Deployment completed successfully!")
            print("   Your MuBench app is now running in Kubernetes!")
        else:
            print("\n❌ Deployment failed!")
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Deployment interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 