"""Release candidate, test suite registry and the fail-closed gate (spec 6.3, 9)."""

from skuld.release.gate import CaseEvidence, decide
from skuld.release.registry import (
    PolicyRegistry,
    RegressionTest,
    TestSuite,
    build_suite,
    regression_from_counterexample,
)

__all__ = [
    "CaseEvidence",
    "PolicyRegistry",
    "RegressionTest",
    "TestSuite",
    "build_suite",
    "decide",
    "regression_from_counterexample",
]
