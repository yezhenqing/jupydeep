"""
Pytest configuration and shared fixtures for JupyDeep tests.

This module provides:
- jupyter_server fixture: Jupyter Lab server
"""

import pytest

pytest_plugins = ["pytest_jupyter.jupyter_server"]


@pytest.fixture
def jp_server_config(jp_server_config):

    if "ServerApp" not in jp_server_config:
        jp_server_config["ServerApp"] = {}
    
    if "jpserver_extensions" not in jp_server_config["ServerApp"]:
        jp_server_config["ServerApp"]["jpserver_extensions"] = {}
    
    jp_server_config["ServerApp"]["jpserver_extensions"]["jupydeep"] = True
    
    return jp_server_config


@pytest.fixture
def jp_base_url():
    return "/"