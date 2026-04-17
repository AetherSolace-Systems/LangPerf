"""LangPerf span-attribute keys — public contract.

Canonical strings the SDK stamps on every span. The backend, tests, and
demo scripts reach for these constants instead of hardcoding "langperf.*".
Kept deliberately in sync with `api/app/constants.py` in the backend — both
modules duplicate the strings so neither side takes a cross-project import
dependency on the other.
"""

TRAJECTORY_ID = "langperf.trajectory.id"
TRAJECTORY_NAME = "langperf.trajectory.name"
NODE_KIND = "langperf.node.kind"
NODE_NAME = "langperf.node.name"
NOTE = "langperf.note"
