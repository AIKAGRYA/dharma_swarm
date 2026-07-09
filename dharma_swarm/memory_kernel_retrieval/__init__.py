"""Decomposition seam for the governed retrieval engine's scoring helpers.

``dharma_swarm.memory_retrieval`` remains the public door (``GovernedRetrievalEngine``,
``RetrievalQuery``, etc.); this package holds the private scoring/matching
helpers split out to keep ``memory_retrieval.py`` under the Rule 10 module
line budget. Nothing outside ``memory_retrieval.py`` should import from here
directly.
"""

from __future__ import annotations
