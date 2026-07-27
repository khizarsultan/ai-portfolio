"""MLflow tracking + model-registry wrapper (MLflow 3.x, alias-based).

The registry is the single source of truth: every model version links to its training
run, metrics, dataset lineage, and decision threshold (stored as version tags). The
current champion carries the `production` alias; a candidate under review carries
`challenger`. Aliases replace the deprecated Staging/Production *stages*.
"""
from __future__ import annotations
import os
import sys
import json
import tempfile
import numpy as np
import joblib
import mlflow
from mlflow import MlflowClient
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

_TAG_KEYS = ("threshold", "model_name", "feature_names")


def client() -> MlflowClient:
    mlflow.set_tracking_uri(C.TRACKING_URI)
    mlflow.set_experiment(C.EXPERIMENT)
    # Capture host telemetry (CPU/RAM/disk) during training runs. Fast sampling so even
    # short sklearn fits record at least one tick into the run's System metrics tab.
    try:
        mlflow.enable_system_metrics_logging()
        mlflow.set_system_metrics_sampling_interval(1)
        mlflow.set_system_metrics_samples_before_logging(1)
    except Exception:
        pass
    return MlflowClient(tracking_uri=C.TRACKING_URI)


def _pipe(artifact: dict) -> Pipeline:
    """A single inference object = fitted preprocessor + fitted model."""
    return Pipeline([("pre", artifact["preprocessor"]), ("clf", artifact["model"])])


def log_and_register(artifact: dict, metrics: dict, params: dict | None = None,
                     dataset_meta: dict | None = None, run_name: str | None = None,
                     alias: str | None = None) -> str:
    """Log a training run, register a new model version, tag it, optionally set an alias."""
    cl = client()
    with mlflow.start_run(run_name=run_name) as run:
        if params:
            mlflow.log_params(params)
        mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
        if dataset_meta:
            mlflow.log_dict(dataset_meta, "dataset.json")
        with tempfile.TemporaryDirectory() as td:
            ap = os.path.join(td, "artifact.joblib")
            joblib.dump(artifact, ap, compress=3)
            mlflow.log_artifact(ap)                       # exact dashboard-native artifact
        mlflow.sklearn.log_model(_pipe(artifact), artifact_path="model")
        run_id = run.info.run_id

    mv = mlflow.register_model(f"runs:/{run_id}/model", C.REGISTERED_MODEL)
    v = mv.version
    cl.set_model_version_tag(C.REGISTERED_MODEL, v, "threshold", str(artifact.get("threshold", "")))
    cl.set_model_version_tag(C.REGISTERED_MODEL, v, "model_name", artifact["model_name"])
    cl.set_model_version_tag(C.REGISTERED_MODEL, v, "feature_names", json.dumps(artifact["feature_names"]))
    for k, val in metrics.items():
        cl.set_model_version_tag(C.REGISTERED_MODEL, v, f"metric_{k}", f"{float(val):.6f}")
    if dataset_meta and dataset_meta.get("version"):
        cl.set_model_version_tag(C.REGISTERED_MODEL, v, "dataset_version", dataset_meta["version"])
    if alias:
        cl.set_registered_model_alias(C.REGISTERED_MODEL, alias, v)
    return v


def register_existing_artifact(artifact: dict, metrics: dict, note: str = "bootstrap") -> str:
    """Bring an already-trained artifact under governance as the first champion."""
    return log_and_register(artifact, metrics, params={"source": note},
                            run_name=f"{note}", alias=C.ALIAS_PROD)


def version_by_alias(alias: str):
    try:
        return client().get_model_version_by_alias(C.REGISTERED_MODEL, alias)
    except Exception:
        return None


def set_alias(alias: str, version: str):
    client().set_registered_model_alias(C.REGISTERED_MODEL, alias, version)


def delete_alias(alias: str):
    try:
        client().delete_registered_model_alias(C.REGISTERED_MODEL, alias)
    except Exception:
        pass


def load_artifact(alias_or_version: str) -> dict | None:
    """Rebuild the dashboard-native artifact dict from a registered version."""
    cl = client()
    if str(alias_or_version).isdigit():
        mv = cl.get_model_version(C.REGISTERED_MODEL, str(alias_or_version))
    else:
        mv = version_by_alias(alias_or_version)
    if mv is None:
        return None
    pipe = mlflow.sklearn.load_model(f"models:/{C.REGISTERED_MODEL}/{mv.version}")
    tags = mv.tags
    return {"model": pipe.named_steps["clf"], "preprocessor": pipe.named_steps["pre"],
            "threshold": float(tags.get("threshold") or 0.5),
            "feature_names": json.loads(tags.get("feature_names", "[]")),
            "model_name": tags.get("model_name", "model"), "version": mv.version, "tags": tags}


def list_versions() -> list[dict]:
    cl = client()
    try:
        versions = cl.search_model_versions(f"name='{C.REGISTERED_MODEL}'")
    except Exception:
        return []
    prod = version_by_alias(C.ALIAS_PROD)
    chal = version_by_alias(C.ALIAS_CHALLENGER)
    prod_v = prod.version if prod else None
    chal_v = chal.version if chal else None
    out = []
    for mv in sorted(versions, key=lambda m: int(m.version)):
        aliases = [a for a, vv in [(C.ALIAS_PROD, prod_v), (C.ALIAS_CHALLENGER, chal_v)] if vv == mv.version]
        out.append({"version": mv.version, "aliases": aliases,
                    "roc_auc": mv.tags.get("metric_macro_f1", ""),
                    "pr_auc": mv.tags.get("metric_macro_recall", ""),
                    "dataset": mv.tags.get("dataset_version", ""),
                    "model_name": mv.tags.get("model_name", "")})
    return out
