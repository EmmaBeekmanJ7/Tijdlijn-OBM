"""
Entrypoint for generating summaries for a timeline or a single document.

This script uses the `Timeline` service to update summaries in OpenSearch.

Usage:
    - To summarize all documents in a timeline, provide only `tijdlijn_id`.
    - To summarize a specific document, also provide `doc_id`.

Raises:
    TimelineNotFound:
        If the specified timeline cannot be found in OpenSearch.
"""

from resource_classes.services.timeline import Timeline
from resource_classes import TimelineNotFound

if __name__ == "__main__":

    try:
        Timeline().summarize()
    except TimelineNotFound as e:
        print(f"Timeline could not be found: {e}")
