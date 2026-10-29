"""Search: random baseline (skuld.core.protocol), active search, minimizer, plots.

Nothing in this package imports the simulator. Strategies see only an
`Objective` callable and `EpisodeStatus` values; the oracle owns every verdict.
"""

from skuld.search.active import ActiveSearchConfig, SearchResult, active_search
from skuld.search.minimize import MinimizationConfig, MinimizationResult, minimize_failure
from skuld.search.objective import Candidate, CurvePoint, Ledger, Objective, Outcome

__all__ = [
    "ActiveSearchConfig",
    "Candidate",
    "CurvePoint",
    "Ledger",
    "MinimizationConfig",
    "MinimizationResult",
    "Objective",
    "Outcome",
    "SearchResult",
    "active_search",
    "minimize_failure",
]
