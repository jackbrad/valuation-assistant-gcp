#!/usr/bin/env python3
"""Deployment script for Cloud Run service val-valuation-app.

Builds and deploys the Appraisal AI service to Google Cloud Run in us-central1.
"""
import os
import subprocess
import sys
import time
from pathlib import Path
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import settings

def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n[EXEC] {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {res.returncode}")
    return res

def main():
    project_id = settings["project"]["project_id"]
    region = settings["project"].get("region", "us-central1")
    service_name = "val-valuation-app"
    
    print(f"==================================================")
    print(f"Deploying {service_name} to Google Cloud Run")
    print(f"Project: {project_id}")
    print(f"Region:  {region}")
    print(f"==================================================")
    
    # 1. Check for gcloud executable
    gcloud_bin = None
    for candidate in ["gcloud", "/opt/homebrew/bin/gcloud", "/opt/homebrew/share/google-cloud-sdk/bin/gcloud"]:
        try:
            res = subprocess.run([candidate, "--version"], capture_output=True, text=True)
            if res.returncode == 0:
                gcloud_bin = candidate
                break
        except Exception:
            continue
            
    if not gcloud_bin:
        print("[!] Error: gcloud CLI not found in PATH or standard Homebrew locations.")
        print("Falling back to local application serving per FIXES.md fallback clause.")
        sys.exit(1)

    print(f"Using gcloud binary: {gcloud_bin}")
    
    # 2. Deploy to Cloud Run using source deploy
    deploy_cmd = [
        gcloud_bin,
        "run",
        "deploy",
        service_name,
        "--source",
        str(PROJECT_ROOT),
        "--project",
        project_id,
        "--region",
        region,
        "--min-instances",
        "1",
        # DEMO-SHORTCUT: review queue and corrections live in memory, so keep one instance.
        # Production writes them to BigQuery (val_ops) and can scale out.
        "--max-instances",
        "1",
        "--allow-unauthenticated",
        "--quiet",
    ]
    
    try:
        run_cmd(deploy_cmd)
    except Exception as e:
        print(f"[!] Deployment failed: {e}")
        print("Per FIXES.md: If deploy is blocked, stop; local is the fallback.")
        sys.exit(1)
        
    # 3. Retrieve service URL
    url_cmd = [
        gcloud_bin,
        "run",
        "services",
        "describe",
        service_name,
        "--project",
        project_id,
        "--region",
        region,
        "--format",
        "value(status.url)",
    ]
    res = run_cmd(url_cmd)
    service_url = res.stdout.strip()
    print(f"\n[OK] Service deployed at: {service_url}")
    
    # 4. Verify health/status
    endpoints = [f"{service_url}/health", f"{service_url}/healthz"]
    print(f"Verifying service health on {service_url}...")
    success = False
    for ep in endpoints:
        try:
            req = urllib.request.Request(ep, headers={"User-Agent": "DeployCheck/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.getcode()
                print(f"  Endpoint {ep}: HTTP {code}")
                if code == 200:
                    success = True
        except urllib.error.HTTPError as e:
            print(f"  Endpoint {ep}: HTTP {e.code} (Note: Google Frontend reserves /healthz on *.run.app)")
        except Exception as e:
            print(f"  Endpoint {ep} error: {e}")

    if success:
        print("\nVerification SUCCESS: Cloud Run service is healthy and serving live traffic.")
        return 0
    else:
        print("[!] Warning: Health checks did not return 200.")
        return 1
            
    print("[!] Warning: Health check did not return 200.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
