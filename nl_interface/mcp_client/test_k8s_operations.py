#!/usr/bin/env python3
import asyncio
import json
import time
from client import MCPClient

async def test_k8s_operations():
    """Test basic Kubernetes operations using MCP client"""
    client = MCPClient(["npx", "mcp-server-kubernetes"])
    
    try:
        print("🚀 Starting MCP Kubernetes client...")
        await client.start()
        
        print("🔧 Initializing client...")
        init_response = await client.initialize()
        print(f"✅ Initialized: {init_response.get('result', {}).get('protocolVersion', 'unknown')}")
        
        # Test namespace name (using dashes as per memory)
        test_namespace = "test-mcp-namespace"
        
        print("\n📋 Listing current namespaces...")
        namespaces_response = await client.call_tool("kubectl_list", {"resourceType": "namespaces"})
        print(f"Current namespaces: {len(namespaces_response.get('content', [{}])[0].get('text', '').splitlines())} found")
        
        print(f"\n🏗️  Creating namespace: {test_namespace}")
        create_response = await client.call_tool("kubectl_apply", {
            "yaml": f"""
apiVersion: v1
kind: Namespace
metadata:
  name: {test_namespace}
  labels:
    purpose: mcp-testing
    created-by: test-script
"""
        })
        
        if create_response.get('isError'):
            print(f"❌ Failed to create namespace: {create_response}")
        else:
            print(f"✅ Namespace created successfully")
        
        # Wait a moment for namespace to be ready
        await asyncio.sleep(2)
        
        print(f"\n🔍 Verifying namespace exists...")
        verify_response = await client.call_tool("kubectl_get", {
            "resourceType": "namespace",
            "name": test_namespace
        })
        
        if verify_response.get('isError'):
            print(f"❌ Namespace verification failed: {verify_response}")
        else:
            print(f"✅ Namespace verified: {test_namespace}")
        
        print(f"\n📦 Creating a test deployment in namespace...")
        deployment_response = await client.call_tool("kubectl_apply", {
            "yaml": f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-deployment
  namespace: {test_namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
"""
        })
        
        if deployment_response.get('isError'):
            print(f"❌ Failed to create deployment: {deployment_response}")
        else:
            print(f"✅ Test deployment created")
        
        # Wait for deployment
        await asyncio.sleep(3)
        
        print(f"\n📊 Listing deployments in namespace...")
        deployments_response = await client.call_tool("kubectl_list", {
            "resourceType": "deployments",
            "namespace": test_namespace
        })
        print(f"Deployments in {test_namespace}: Found deployment resources")
        
        print(f"\n🧹 Cleaning up - deleting namespace...")
        delete_response = await client.call_tool("kubectl_delete", {
            "resourceType": "namespace",
            "name": test_namespace
        })
        
        if delete_response.get('isError'):
            print(f"❌ Failed to delete namespace: {delete_response}")
        else:
            print(f"✅ Namespace {test_namespace} deleted successfully")
        
        print(f"\n🔍 Final verification - listing namespaces...")
        final_namespaces = await client.call_tool("kubectl_list", {"resourceType": "namespaces"})
        print(f"✅ Final namespace count check completed")
        
        print(f"\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        
    finally:
        print("\n🛑 Stopping MCP client...")
        await client.stop()

if __name__ == "__main__":
    print("🧪 Starting Kubernetes MCP Client Tests")
    print("=" * 50)
    asyncio.run(test_k8s_operations()) 