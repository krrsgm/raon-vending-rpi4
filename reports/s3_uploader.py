"""S3 uploader and presigned URL helper.

This module provides two conveniences:
- upload_file_to_s3(file_path, bucket, key=None, region=None, extra_args=None)
- generate_presigned_url(bucket, key, expires_in=3600, region=None)

It uses boto3 if available; otherwise it raises a RuntimeError and explains how to install it.
Environment credentials are preferred (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) or an IAM role on the host.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception as e:
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception


def _require_boto3():
    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 uploads. Install with 'pip install boto3'.")


def upload_file_to_s3(file_path: str or Path, bucket: str, key: Optional[str] = None, region: Optional[str] = None, extra_args: Optional[dict] = None) -> str:
    """Upload a file to S3 and return the object key.

    Args:
        file_path: path to local file
        bucket: S3 bucket name
        key: optional S3 key (defaults to file name under 'reports/' prefix)
        region: AWS region (optional)
        extra_args: extra args for upload_file (e.g., ACL)

    Returns:
        key used on S3
    """
    _require_boto3()

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    key = key or f"reports/{p.name}"

    session = boto3.session.Session()
    s3 = session.client('s3', region_name=region) if region else session.client('s3')

    try:
        s3.upload_file(str(p), bucket, key, ExtraArgs=extra_args or {})
        return key
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Failed to upload {p} to s3://{bucket}/{key}: {e}")


def generate_presigned_url(bucket: str, key: str, expires_in: int = 3600, region: Optional[str] = None) -> str:
    """Generate a presigned GET URL for an S3 object.

    Returns the URL string.
    """
    _require_boto3()

    session = boto3.session.Session()
    s3 = session.client('s3', region_name=region) if region else session.client('s3')

    try:
        url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=int(expires_in))
        return url
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Failed to generate presigned URL for s3://{bucket}/{key}: {e}")
