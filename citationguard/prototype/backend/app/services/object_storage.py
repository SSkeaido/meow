import os
from pathlib import Path


class ObjectStorage:
    def __init__(self) -> None:
        self.provider = os.getenv("OBJECT_STORAGE_PROVIDER", "local").lower()

    def save(self, content: bytes, key: str) -> str:
        if self.provider == "local":
            root = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
            target = root / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return str(target)
        if self.provider != "s3":
            raise ValueError("OBJECT_STORAGE_PROVIDER must be 'local' or 's3'")

        import boto3

        bucket = _required("S3_BUCKET")
        client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            region_name=os.getenv("S3_REGION") or None,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY") or None,
        )
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType="application/pdf",
            ServerSideEncryption=os.getenv("S3_SERVER_SIDE_ENCRYPTION") or "AES256",
        )
        return f"s3://{bucket}/{key}"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for S3 object storage")
    return value


object_storage = ObjectStorage()
