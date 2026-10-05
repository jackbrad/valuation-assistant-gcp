"""Enable required Google Cloud APIs for the project."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import settings
import google.auth
from google.auth.transport.requests import Request
import requests

def enable_apis():
    project_id = settings["project"]["project_id"]
    print(f"Enabling required APIs for project: {project_id}...")

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())

    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }

    apis = [
        "pubsub.googleapis.com",
        "documentai.googleapis.com",
        "aiplatform.googleapis.com",
        "bigqueryconnection.googleapis.com",
        "run.googleapis.com",
        "cloudresourcemanager.googleapis.com",
    ]

    for api in apis:
        url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services/{api}:enable"
        resp = requests.post(url, headers=headers)
        if resp.status_code == 200:
            print(f"  + Enabled: {api}")
        else:
            try:
                err = resp.json().get("error", {}).get("message", resp.text)
                print(f"  ! {api}: {resp.status_code} - {err}")
            except Exception:
                print(f"  ! {api}: {resp.status_code} - {resp.text[:100]}")

if __name__ == "__main__":
    enable_apis()
