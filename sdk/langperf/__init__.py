"""LangPerf Python SDK — tracer for agent trajectories.

M1 surface: `init()` and `flush()`. `trajectory()` and `node()` arrive in M4.
"""

from langperf.tracer import flush, init

__all__ = ["init", "flush"]
__version__ = "0.1.0"
