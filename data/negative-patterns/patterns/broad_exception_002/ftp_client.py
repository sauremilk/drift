import logging

logger = logging.getLogger(__name__)


def download(host, path):
    try:
        return b""
    except Exception:
        logger.error("FTP download failed")
