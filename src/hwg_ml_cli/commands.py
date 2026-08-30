"""
CLI command implementations for exercises and lectures.
"""

from pathlib import Path

import click

from hwg_ml_cli.api import (
    fetch_course_data,
    fetch_exercise_files,
    fetch_lecture_files,
    process_course_items,
)
from hwg_ml_cli.config import DEFAULT_COURSE
from hwg_ml_cli.download import (
    download_and_extract_file,
    download_lecture_file,
    extract_exercise_number,
)


def update_exercises(output, course):
    """Download new exercises from the H4HN CMS API."""
    click.echo(f"Fetching course: {course}...")

    # Fetch course data
    target_course, error = fetch_course_data(course)
    if error:
        click.echo(f"❌ Error: {error}", err=True)
        return 1

    # Fetch and sort exercises
    exercises_with_files, error = process_course_items(
        target_course, "exercise", fetch_exercise_files
    )
    if error:
        click.echo(f"❌ Error: {error}", err=True)
        return 0 if "No exercise" in error else 1

    # Create output directory
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Process each exercise
    for exercise in exercises_with_files:
        topic = exercise.get("topic", "Unknown")
        files = exercise.get("files", [])

        if not files:
            click.echo(f"  ⚠️  {topic}: No files available")
            continue

        click.echo(f"  📦 {topic}: {len(files)} file(s)")

        for file_info in files:
            file_name = file_info.get("name", "unknown.zip")
            exercise_num = extract_exercise_number(file_name)

            if not exercise_num:
                click.echo(
                    f"      ⚠️  Skipping {file_name} - couldn't determine exercise number"
                )
                continue

            # Download and extract file
            result = download_and_extract_file(file_info, exercise_num, output_path)
            click.echo(f"      {result}")

    click.echo(f"\n✓ All exercises extracted to {output_path}")
    return 0


def update_lectures(output, course):
    """Download lecture slides from the H4HN CMS API."""
    click.echo(f"Fetching course: {course}...")

    # Fetch course data
    target_course, error = fetch_course_data(course)
    if error:
        click.echo(f"❌ Error: {error}", err=True)
        return 1

    # Fetch and sort lectures
    lectures_with_files, error = process_course_items(
        target_course, "lecture", fetch_lecture_files
    )
    if error:
        click.echo(f"❌ Error: {error}", err=True)
        return 0 if "No lecture" in error else 1

    # Create output directory
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Process each lecture
    downloaded_count = 0
    for lecture in lectures_with_files:
        topic = lecture.get("topic", "Unknown")
        files = lecture.get("files", [])

        if not files:
            continue

        # Filter for PDF files
        pdf_files = [f for f in files if f.get("name", "").lower().endswith(".pdf")]

        if not pdf_files:
            continue

        click.echo(f"  📄 {topic}: {len(pdf_files)} PDF(s)")

        for file_info in pdf_files:
            result = download_lecture_file(file_info, output_path)
            click.echo(f"      {result}")
            if "✓" in result:
                downloaded_count += 1

    if downloaded_count > 0:
        click.echo(
            f"\n✓ {downloaded_count} lecture slide(s) downloaded to {output_path}"
        )
    else:
        click.echo(f"\n⏭️  All lecture slides already downloaded in {output_path}")
    return 0
