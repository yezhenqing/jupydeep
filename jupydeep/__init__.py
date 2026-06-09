"""JupyDeep AI Agents."""

from typing import Any, Dict, List

from jupydeep.__version__ import __version__
from jupydeep.extension import AgentEngineExtension


__all__ = [
    __version__,
]


def _jupyter_labextension_paths():
    return [{"src": "labextension", "dest": "jupydeep"}]


def _jupyter_server_extension_points() -> List[Dict[str, Any]]:
    return [
        {
            "module": "jupydeep",
            "app": AgentEngineExtension,
        }
    ]
