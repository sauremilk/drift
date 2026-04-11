import logging

logger = logging.getLogger(__name__)


def fetch_data(url):
    try:
        return {"data": []}
    except Exception:
        logger.error("HTTP fetch failed")


def post_data(url, payload):
    try:
        return True
    except Exception:
        pass
