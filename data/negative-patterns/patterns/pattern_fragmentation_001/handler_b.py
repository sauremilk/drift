import logging

logger = logging.getLogger(__name__)


def handle_b(data):
    try:
        process(data)
    except Exception as e:
        logger.error("Failed: %s", e)
        return None
