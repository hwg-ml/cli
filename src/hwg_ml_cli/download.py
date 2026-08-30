"""
Download and extraction utilities for exercise and lecture files.
"""

import re
import zipfile
from io import BytesIO

import requests

from hwg_ml_cli.config import BASE_URL


def extract_exercise_number(filename):
    """Extract exercise number from filename (e.g., 'e03_solution.zip' -> 'e03')."""
    match = re.match(r"(e\d+)", filename)
    return match.group(1) if match else None


def is_already_downloaded(exercise_dir, exercise_num, is_solution):
    """Check if exercise files are already downloaded."""
    if is_solution:
        marker = exercise_dir / "Solution"
        return marker.exists() and any(marker.iterdir())
    else:
        task_marker = exercise_dir / "Task"
        explanation_files = (
            list(exercise_dir.glob(f"{exercise_num}_explanation.*"))
            if exercise_dir.exists()
            else []
        )
        return (
            task_marker.exists() and any(task_marker.iterdir())
        ) or explanation_files


def extract_zip_file(zip_content, exercise_num, exercise_dir, output_path):
    """Extract zip file contents to appropriate directory."""
    with zipfile.ZipFile(BytesIO(zip_content)) as zip_ref:
        for zip_info in zip_ref.filelist:
            # Skip macOS metadata files and directories
            if "__MACOSX" in zip_info.filename or "._" in zip_info.filename:
                continue
            if zip_info.is_dir():
                continue

            # Determine target path based on zip structure
            if zip_info.filename.startswith(f"{exercise_num}/"):
                target_path = output_path / zip_info.filename
            else:
                target_path = exercise_dir / zip_info.filename

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(zip_ref.read(zip_info.filename))


def download_and_extract_file(file_info, exercise_num, output_path):
    """Download and extract a single exercise file."""
    file_url = BASE_URL + file_info.get("url", "")
    file_name = file_info.get("name", "unknown.zip")
    exercise_dir = output_path / exercise_num

    # Check if already downloaded
    is_solution = "solution" in file_name.lower()
    if is_already_downloaded(exercise_dir, exercise_num, is_solution):
        return f"⏭️  {file_name} - already downloaded"

    # Download file
    response = requests.get(file_url)
    if response.status_code != 200:
        return f"❌ Failed to download {file_name}"

    # Extract or save file
    try:
        if file_name.endswith(".zip"):
            extract_zip_file(response.content, exercise_num, exercise_dir, output_path)
        else:
            target_path = exercise_dir / file_name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(response.content)
        return f"✓ {file_name}"
    except Exception as e:
        return f"❌ Error processing {file_name}: {str(e)}"


def download_lecture_file(file_info, output_path):
    """Download a single lecture PDF file."""
    file_url = BASE_URL + file_info.get("url", "")
    file_name = file_info.get("name", "unknown.pdf")
    target_path = output_path / file_name

    # Check if already downloaded
    if target_path.exists():
        return f"⏭️  {file_name} - already downloaded"

    # Download file
    response = requests.get(file_url)
    if response.status_code != 200:
        return f"❌ Failed to download {file_name}"

    # Save file
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(response.content)
        return f"✓ {file_name}"
    except Exception as e:
        return f"❌ Error saving {file_name}: {str(e)}"
