import logging

logger = logging.getLogger(__name__)


def invalidate(key):
    try:
        return True
    except Exception:
        logger.error("cache invalidate failed")
