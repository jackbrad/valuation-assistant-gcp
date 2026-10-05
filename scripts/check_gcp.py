"""Check GCP authentication and project configuration."""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from config.loader import settings

def main():
    project_id = settings["project"]["project_id"]
    print(f"Target GCP Project ID: {project_id}")
    
    try:
        credentials, default_project = google.auth.default()
        print(f"Credentials located successfully: {type(credentials).__name__}")
        if default_project:
            print(f"Default project from credentials: {default_project}")
        print("GCP authentication: OK")
        return 0
    except DefaultCredentialsError as e:
        print("\n[!] No Google Cloud Application Default Credentials found.")
        print("To authenticate:")
        print("  Option A (User): Run `gcloud auth application-default login`")
        print("  Option B (Service Account): Set `export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`")
        print(f"Details: {e}\n")
        return 1
    except Exception as e:
        print(f"Authentication error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
