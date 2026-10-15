
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tds-network-games.sanand.workers.dev",
    ],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def coerce(key, value):
    value = str(value)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return value.strip().lower() in ("true", "1", "yes", "on")

    return value


def normalize_layer(layer):
    normalized = {}

    for key, value in layer.items():
        if value is None:
            continue

        key = str(key).lower()

        if key == "num_workers":
            key = "workers"
        elif key.startswith("app_"):
            key = key[4:]

        normalized[key] = value

    return normalized


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    # Layer 1: hardcoded defaults
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    env_name = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{env_name}.yaml"

    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        config.update(normalize_layer(yaml_config))

    # Layer 3: .env file
    env_file = dotenv_values(BASE_DIR / ".env")
    config.update(normalize_layer(env_file))

    # Layer 4: actual OS environment variables.
    # Only APP_* variables belong to this layer.
    os_config = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    config.update(normalize_layer(os_config))

    # Layer 5: query-string CLI overrides.
    # Split only at the first "=" so values may contain "=".
    for item in set:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        key = key.strip().lower()

        if key.startswith("app_"):
            key = key[4:]
        if key == "num_workers":
            key = "workers"

        if key:
            config[key] = value

    # Apply consistent types after all layers have been merged.
    result = {
        key: coerce(key, value)
        for key, value in config.items()
    }

    # Never return the real secret.
    if "api_key" in result:
        result["api_key"] = "****"

    return result
