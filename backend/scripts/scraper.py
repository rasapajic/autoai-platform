"""
AutoAI scraper entrypoint — intentionally disabled.

Historical scraper code remains available in Git history. This executable is
a no-op until every source used by AutoAI has documented commercial rights.
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    logger.warning(
        "AutoAI external data updates are disabled; no listings were fetched or changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
