import logging

logger = logging.getLogger(__name__)


def get_user(uid):
    try:
        return {"id": uid}
    except Exception:
        logger.error("db get failed")
