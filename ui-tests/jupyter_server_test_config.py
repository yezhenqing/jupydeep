from jupyterlab.galata import configure_jupyter_server

# ruff: noqa: F821
c = get_config()  # type: ignore[name-defined]

configure_jupyter_server(c)

# Uncomment to set server log level to debug level
# c.ServerApp.log_level = "DEBUG"
