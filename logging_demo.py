
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

logger.debug("This is a debug message")
logger.info("Agent started")
logger.warning("Maximum steps approaching")
logger.error("Tool execution failed")

print("Program finished")
