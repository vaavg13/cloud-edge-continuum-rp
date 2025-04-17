# This script does not work. Work in progress.
import requests
import json

GRAFANA_URL = "http://localhost:30000"  # NodePort or ClusterIP
API_KEY = "admin:admin"  # Or use an API token

with open("my-dashboard.json") as f:
    dashboard_json = json.load(f)

payload = {
    "dashboard": dashboard_json,
    "overwrite": True,
    "folderId": 0
}

response = requests.post(
    f"{GRAFANA_URL}/api/dashboards/db",
    json=payload,
    auth=("admin", "admin")  # Or use headers={"Authorization": "Bearer <API_KEY>"}
)

print(response.status_code, response.text)