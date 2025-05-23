"""
Simple connectivity test for edge endpoints
"""
import requests
import time

def test_edge_endpoints():
    """Test connectivity to edge endpoints."""
    base_host = "172.23.0.5"
    ports = [31115, 31116]
    sites = ["edge-site-1", "edge-site-2"]
    
    print("Testing Edge Endpoint Connectivity")
    print("=" * 40)
    
    for port in ports:
        for site in sites:
            url = f"http://{base_host}:{port}/s0-{site}"
            try:
                print(f"Testing {url}...", end=" ")
                start_time = time.time()
                response = requests.get(url, timeout=5)
                duration = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    print(f"OK (HTTP {response.status_code}, {duration:.0f}ms)")
                else:
                    print(f"Failed (HTTP {response.status_code}, {duration:.0f}ms)")
                        
            except requests.exceptions.ConnectException as e:
                print(f"Connection failed: {e}")
            except requests.exceptions.Timeout:
                print(f"Timeout (>5s)")
            except Exception as e:
                print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_edge_endpoints() 