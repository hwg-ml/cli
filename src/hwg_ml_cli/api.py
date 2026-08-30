"""
API client functions for fetching course data from the H4HN CMS.
"""

import click
import requests

from hwg_ml_cli.config import API_COURSES, API_LECTURES


def fetch_course_data(course_name):
    """Fetch course data from API and return the target course."""
    response = requests.get(API_COURSES, params={"populate": "lectures"})

    if response.status_code != 200:
        return (
            None,
            f"Failed to fetch data from API (status code: {response.status_code})",
        )

    courses = response.json().get("data", [])

    # Find matching course
    for course in courses:
        if course.get("name") == course_name or course.get("slug") == course_name:
            return course, None

    # Course not found - prepare error message with available courses
    available = "\n".join(
        [f"  - {c.get('name')} (slug: {c.get('slug')})" for c in courses]
    )
    return None, f"Course '{course_name}' not found\n\nAvailable courses:\n{available}"


def fetch_exercise_files(exercise_ids):
    """Fetch detailed exercise data with files from API."""
    response = requests.get(
        API_LECTURES,
        params={
            "filters[documentId][$in]": exercise_ids,
            "filters[type][$eq]": "exercise",
            "populate": "*",
        },
    )

    if response.status_code != 200:
        return (
            None,
            f"Failed to fetch exercise files (status code: {response.status_code})",
        )

    return response.json().get("data", []), None


def fetch_lecture_files(lecture_ids):
    """Fetch detailed lecture data with files from API."""
    response = requests.get(
        API_LECTURES,
        params={
            "filters[documentId][$in]": lecture_ids,
            "filters[type][$eq]": "lecture",
            "populate": "*",
        },
    )

    if response.status_code != 200:
        return (
            None,
            f"Failed to fetch lecture files (status code: {response.status_code})",
        )

    return response.json().get("data", []), None


def process_course_items(course, item_type, fetch_func):
    """Common logic to fetch and sort course items (exercises or lectures)."""
    # Get items from course
    all_lectures = course.get("lectures", [])
    items = [l for l in all_lectures if l.get("type") == item_type]

    if not items:
        return None, f"No {item_type}s found in course: {course.get('name')}"

    click.echo(f"Found {len(items)} {item_type}(s) in course: {course.get('name')}")
    click.echo(f"Fetching {item_type} files...")

    # Fetch detailed data with files
    item_ids = [item.get("documentId") for item in items]
    items_with_files, error = fetch_func(item_ids)

    if error:
        return None, error

    if not items_with_files:
        return None, f"No {item_type}s found."

    # Sort by start date
    items_with_files.sort(key=lambda x: x.get("start", ""))

    return items_with_files, None
