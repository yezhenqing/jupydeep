import asyncio
from ..utils.logging import get_logger
# from jupyter_core.utils import run_sync

logger = get_logger(__name__)


# Simulate a global configuration change trigger
class EngineWatcher:
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        pass

    @classmethod
    async def get_instance(cls) -> "EngineWatcher":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance.event = asyncio.Event()
                    instance.last_data = None
                    instance._initialized = True
                    cls._instance = instance
        return cls._instance

    def notify(self, data):
        """Notify all waiting handlers of configuration change"""
        if self._instance is None or not getattr(self, "_initialized", False):
            logger.error(
                "EngineWatcher is not initialized! Ensure it is ready before invoking notify."
            )
            return

        self.last_data = data
        self.event.set()
        # Clear the event in the next event loop tick to ensure all wait() have completed
        asyncio.get_running_loop().call_soon(self.event.clear)


async def get_watcher():
    return await EngineWatcher.get_instance()


# watcher = run_sync(get_watcher)()
