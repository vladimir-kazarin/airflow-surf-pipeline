"""Load the published dataset: S3 first, bundled snapshot as fallback.

The fallback keeps the portfolio demo alive even if AWS credentials are missing
or S3 is unreachable; the page says which source it is showing.
"""

import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st
from surf_lib import publish

logger = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).parent / "sample"
SOURCE_S3 = "s3"
SOURCE_SAMPLE = "bundled snapshot"


@dataclass(frozen=True)
class Dataset:
    conditions: pd.DataFrame
    meta: dict
    runs: pd.DataFrame
    source: str
    warning: str | None = None


def _s3_config() -> dict | None:
    """AWS settings from Streamlit secrets ([aws] table), or None if not configured."""
    try:
        aws = st.secrets.get("aws")
    except FileNotFoundError:  # no secrets.toml at all (local dev, tests)
        return None
    except Exception as exc:  # malformed secrets must not take the app down
        logger.warning("Could not read Streamlit secrets: %s", exc)
        return None
    if not aws or not aws.get("bucket"):
        return None
    return dict(aws)


def _load_from_s3(cfg: dict) -> Dataset:
    import boto3  # imported lazily: only needed when S3 is configured

    s3 = boto3.client(
        "s3",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
        region_name=cfg.get("region", "us-east-1"),
    )

    def read(key: str) -> bytes:
        return s3.get_object(Bucket=cfg["bucket"], Key=key)["Body"].read()

    return Dataset(
        conditions=pd.read_csv(io.BytesIO(read(publish.SERVING_KEY))),
        meta=json.loads(read(publish.META_KEY)),
        runs=pd.read_csv(io.BytesIO(read(publish.RUNS_KEY))),
        source=SOURCE_S3,
    )


def _load_from_dir(directory: Path, warning: str | None) -> Dataset:
    return Dataset(
        conditions=pd.read_csv(directory / Path(publish.SERVING_KEY).name),
        meta=json.loads((directory / Path(publish.META_KEY).name).read_text()),
        runs=pd.read_csv(directory / Path(publish.RUNS_KEY).name),
        source=SOURCE_SAMPLE,
        warning=warning,
    )


def load_dataset() -> Dataset:
    explicit_dir = os.environ.get("SURF_DATA_DIR")  # offline mode / tests: never touch S3
    local_dir = Path(explicit_dir or SAMPLE_DIR)
    cfg = None if explicit_dir else _s3_config()
    if cfg is None:
        return _load_from_dir(local_dir, warning=None)

    try:
        return _load_from_s3(cfg)
    except Exception as exc:  # any S3/network/parse failure -> degrade, don't crash
        logger.exception("Loading from S3 failed; using bundled snapshot")
        return _load_from_dir(
            local_dir,
            warning=f"Live data is unavailable right now ({type(exc).__name__}); showing a bundled snapshot.",
        )
