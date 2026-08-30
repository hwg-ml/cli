"""
CLI for submitting files to the submission platform using presigned URLs.
Supports multipart upload for large files (> 50MB).
"""

import os
import tempfile
import zipfile
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm


# 50MB chunk size for multipart uploads
CHUNK_SIZE = 50 * 1024 * 1024
# Threshold for using multipart upload (50MB)
MULTIPART_THRESHOLD = 50 * 1024 * 1024
MULTIPART_CONCURRENCY = 4


class PartFileReader:
    """Wrapper for reading a specific part of a file with progress tracking."""

    def __init__(self, file_obj, size, progress_bar):
        self.file = file_obj
        self.remaining = size
        self.bar = progress_bar

    def read(self, size=-1):
        if self.remaining <= 0:
            return b""

        to_read = self.remaining
        if size >= 0:
            to_read = min(size, self.remaining)

        data = self.file.read(to_read)
        if data:
            read_len = len(data)
            self.remaining -= read_len
            self.bar.update(read_len)
        return data


def print_submission_success(submission_id, version, is_late):
    print(f"✅ Upload complete!")
    print(f"   Submission ID: {submission_id}")
    print(f"   Version: {version}")
    print(f"   Status: {'LATE SUBMISSION' if is_late else 'On time'}")


def create_zip_from_directory(directory_path: Path, output_path: Path = None) -> Path:
    """
    Create a zip file from a directory.

    Args:
        directory_path: Path to the directory to zip
        output_path: Optional path for the output zip file. If not provided,
                    creates a temporary file.

    Returns:
        Path to the created zip file
    """
    if output_path is None:
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(
            suffix=".zip", prefix=f"{directory_path.name}_"
        )
        os.close(fd)
        output_path = Path(temp_path)

    print(f"📦 Zipping directory {directory_path.name}...")

    # Count total files for progress
    total_files = sum(1 for _ in directory_path.rglob("*") if _.is_file())

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        with tqdm(total=total_files, unit="file", desc="📁 Compressing") as pbar:
            for file_path in directory_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(directory_path.parent)
                    zipf.write(file_path, arcname)
                    pbar.update(1)

    zip_size = output_path.stat().st_size
    print(f"✅ Created zip file: {output_path.name} ({zip_size / 1024 / 1024:.2f} MB)")
    return output_path


def submit_file_multipart(
    file_path: Path,
    token: str,
    server_url: str,
) -> dict:
    """
    Submit a large file using multipart upload.

    Args:
        file_path: Path to the file to submit
        token: Access token for authentication
        server_url: URL of the submission server

    Returns:
        Response from the server
    """
    file_size = file_path.stat().st_size
    print(
        f"📦 Preparing multipart upload for {file_path.name} ({file_size / 1024 / 1024:.2f} MB)..."
    )

    # Step 1: Initiate multipart upload
    print("🔑 Initiating multipart upload...")
    response = requests.post(
        f"{server_url}/submit/multipart/initiate",
        data={
            "token": token,
            "filename": file_path.name,
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()

    upload_id = result["upload_id"]
    submission_id = result["submission_id"]
    version = result["version"]
    is_late = result["is_late"]
    object_name = result["object_name"]
    bucket_name = result["bucket_name"]

    print(f"✅ Submission upload initiated (version {version})")

    uploaded_parts = []

    try:
        # Create the progress bar
        with tqdm(
            total=file_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc="📤 Uploading",
        ) as pbar:

            def upload_part(part_number: int, offset: int, size: int) -> dict:
                part_response = requests.post(
                    f"{server_url}/submit/multipart/part",
                    data={
                        "token": token,
                        "upload_id": upload_id,
                        "part_number": str(part_number),
                        "object_name": object_name,
                        "bucket_name": bucket_name,
                    },
                    timeout=30,
                )
                part_response.raise_for_status()
                part_data = part_response.json()
                presigned_url = part_data["presigned_url"]

                with open(file_path, "rb") as part_file:
                    part_file.seek(offset)
                    upload_response = requests.put(
                        presigned_url,
                        data=PartFileReader(part_file, size, pbar),
                        headers={
                            "Content-Type": "application/octet-stream",
                            "Content-Length": str(size),
                        },
                        timeout=300,
                    )
                upload_response.raise_for_status()

                etag = upload_response.headers.get("ETag", "").strip('"')
                return {"part_number": part_number, "etag": etag}

            parts = []
            part_number = 1
            offset = 0
            while offset < file_size:
                size = min(CHUNK_SIZE, file_size - offset)
                parts.append((part_number, offset, size))
                part_number += 1
                offset += size

            with ThreadPoolExecutor(max_workers=MULTIPART_CONCURRENCY) as executor:
                futures = [
                    executor.submit(upload_part, p_num, off, sz)
                    for p_num, off, sz in parts
                ]
                for future in as_completed(futures):
                    uploaded_parts.append(future.result())

        uploaded_parts.sort(key=lambda part: part["part_number"])

        # Step 3: Complete multipart upload
        complete_response = requests.post(
            f"{server_url}/submit/multipart/complete?token={token}",
            json={
                "upload_id": upload_id,
                "object_name": object_name,
                "bucket_name": bucket_name,
                "parts": uploaded_parts,
            },
            headers={
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        complete_response.raise_for_status()

        print_submission_success(submission_id, version, is_late)

        return result

    except Exception as e:
        # Abort multipart upload on error
        print(f"❌ Error during upload, aborting multipart upload...")
        try:
            requests.post(
                f"{server_url}/submit/multipart/abort",
                data={
                    "token": token,
                    "upload_id": upload_id,
                    "object_name": object_name,
                    "bucket_name": bucket_name,
                },
                timeout=30,
            )
        except:
            pass
        raise e


def submit_file(
    file_path: str,
    token: str,
    server_url: str = "https://submissions.h4hn.de",
) -> dict:
    """
    Submit a file or directory to the submission platform using presigned URLs.
    If a directory is provided, it will be zipped before upload.
    Automatically uses multipart upload for files larger than 50MB.

    Args:
        file_path: Path to the file or directory to submit
        token: Access token for authentication
        server_url: URL of the submission server

    Returns:
        Response from the server
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File or directory not found: {file_path}")

    # Handle directory by zipping it first
    temp_zip = None
    if file_path.is_dir():
        temp_zip = create_zip_from_directory(file_path)
        file_path = temp_zip

    try:
        return _submit_file_internal(file_path, token, server_url)
    finally:
        # Clean up temporary zip file if created
        if temp_zip and temp_zip.exists():
            temp_zip.unlink()


def _submit_file_internal(
    file_path: Path,
    token: str,
    server_url: str,
) -> dict:
    """
    Internal function to submit a file to the submission platform.

    Args:
        file_path: Path to the file to submit
        token: Access token for authentication
        server_url: URL of the submission server

    Returns:
        Response from the server
    """

    file_size = file_path.stat().st_size

    # Use multipart upload for large files
    if file_size > MULTIPART_THRESHOLD:
        return submit_file_multipart(file_path, token, server_url)

    # Standard upload for smaller files
    print(
        f"📦 Preparing to submit {file_path.name} ({file_size / 1024 / 1024:.2f} MB)..."
    )

    response = requests.post(
        f"{server_url}/submit",
        data={
            "token": token,
            "filename": file_path.name,
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()

    upload_url = result["upload_url"]
    submission_id = result["submission_id"]
    version = result["version"]
    is_late = result["is_late"]

    with open(file_path, "rb") as f:
        with tqdm.wrapattr(
            f,
            "read",
            total=file_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc="📤 Uploading",
        ) as wrapped_file:
            upload_response = requests.put(
                upload_url,
                data=wrapped_file,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file_size),
                },
                timeout=300,  # 5 minutes timeout for large files
            )
    upload_response.raise_for_status()

    print_submission_success(submission_id, version, is_late)

    return result
