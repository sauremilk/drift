import logging

logger = logging.getLogger(__name__)


def publish(topic, msg):
    try:
        return True
    except Exception:
        logger.error("queue publish failed")
