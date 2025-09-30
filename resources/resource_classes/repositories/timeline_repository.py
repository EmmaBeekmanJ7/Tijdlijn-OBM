"""Timeline Repository"""

from __future__ import annotations

from typing import Dict, List, Optional, Any

from opensearchpy import OpenSearch
from dotenv import load_dotenv

from ..data_models.timeline import Timeline

load_dotenv()


class TimelineRepository:
    """Facilitates repository interactions with `Timeline` objects in OpenSearch."""

    def __init__(self, opensearch: OpenSearch, index: str = "es_timelines"):
        self.opensearch = opensearch
        self.index = index

    @staticmethod
    def _doc_to_source(timeline: Timeline) -> Dict[str, Any]:
        return timeline.to_dict()

    @staticmethod
    def _source_to_doc(source: Dict[str, Any]) -> Timeline:
        return Timeline.from_dict(source)

    def upsert(self, timeline: Timeline) -> None:
        """Updates/creates a `Timeline` object"""

        self.opensearch.index(
            index=self.index,
            id=timeline.identifier,
            body=self._doc_to_source(timeline),
        )

    def get(self, identifier: str) -> Optional[Timeline]:
        """Retrieves a `Timeline` object by it's identifier.

        :param identifier:
            The identifier of the requested `Timeline` object
        """

        try:
            res = self.opensearch.get(index=self.index, id=identifier)
        except Exception:
            return None
        source = res.get("_source")
        return self._source_to_doc(source) if source else None

    def update(self, timeline: Timeline) -> None:
        """Updates a `Timeline` object in Opensearch"""

        self.upsert(timeline)

    def find_all(self, limit: int = 100) -> List[Timeline]:
        """Returns all `Timeline` objects"""

        response = self.opensearch.search(
            index=self.index,
            body={"query": {"match_all": {}}, "size": limit},
        )
        hits = response.get("hits", {}).get("hits", [])
        return [
            self._source_to_doc(hit["_source"]) for hit in hits if hit.get("_source")
        ]
