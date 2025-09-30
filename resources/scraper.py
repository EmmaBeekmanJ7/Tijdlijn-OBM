"""
Entry point for generating a timeline of documents found on OBM.

The script will:
    1. Ask for user input on the search words and document types.
    1. Search for relevant documents based on the user input.
    2. Generate a timeline based on the given search terms and document types. Save it to OpenSearch.
    3. Print the name, id, and #documents of the timeline or an error message if generation fails.
"""

from resource_classes.services.timeline import Timeline
from resource_classes import (
    TimelineNotGenerated,
    DocumentsNotFound,
    TimelineNotInserted,
)

if __name__ == "__main__":
    try:
        # 2. Generate timeline
        timeline = Timeline().generate()

        # 3. Print the generated result
        print("Timeline successfully generated:")

    except TimelineNotGenerated as e:
        print(f"Timeline kon niet gegenereerd worden: {e}")
    except DocumentsNotFound as e:
        print(f"No documents processed: {e}")
    except TimelineNotInserted as e:
        print(f"Timeline could not be inserted: {e}")
    except Exception as e:
        print(f"Onverwachte fout: {e}")
