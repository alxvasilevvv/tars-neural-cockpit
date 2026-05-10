"""Web-search adapters: Brave, DuckDuckGo, SearXNG.

Each adapter exports an ``async search(query, *, limit, …) ->
AdapterResult``. The pack-level dispatcher in ``..actions`` picks one
based on what's configured.
"""

from ._base import AdapterResult, SearchHit, dedupe, trim

__all__ = ["AdapterResult", "SearchHit", "dedupe", "trim"]
