import logging

logger = logging.getLogger(__name__)


def validate_request(req):
    try:
        assert req.get("method"), "method required"
        assert req.get("path"), "path required"
    except AssertionError as e:
        logger.warning("Validation failed: %s", e)
        return None
