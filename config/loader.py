import os
from pathlib import Path
from typing import Any, Dict
import yaml

CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"

# Credentials come from Application Default Credentials: run
# `gcloud auth application-default login` locally; Cloud Run uses its service account.

def load_settings(path: Path | None = None) -> Dict[str, Any]:
    file_path = path or SETTINGS_FILE
    if not file_path.exists():
        example_path = CONFIG_DIR / "settings.example.yaml"
        if example_path.exists():
            with open(example_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        raise FileNotFoundError(f"Settings file not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Global settings instance
settings = load_settings()
