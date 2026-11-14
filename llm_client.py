
import logging
import time

import httpx2

from openai import (
    APIError,
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    RateLimitError,
    AuthenticationError
)

logger = logging.getLogger(__name__)

# Per-phase network timeouts, not an overall Agent deadline.
LLM_TIMEOUT = httpx2.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


def request_llm(client, *, max_attempts=1, **kwargs):
    """Retry transient SDK failures; max_attempts includes the first call.

    Configure the supplied SDK client with max_retries=0 to avoid nested retries.
    Duration includes all attempts and backoff waits. Default preserves one attempt.
    """
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")

    start_time = time.perf_counter()
    response = None
    delay_seconds = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.responses.create(**kwargs)
            break

        except APITimeoutError:
            logger.error("LLM API timeout")

        except APIConnectionError:
            logger.error("LLM API connection failed")

        except RateLimitError:
            logger.warning("LLM API rate limit exceeded")

        except AuthenticationError:
            logger.error("LLM API authentication failed")
            break

        except APIStatusError as e:
            logger.error("LLM API status error: status=%d", e.status_code)
            break

        except APIError:
            logger.error("LLM API unexpected error")
            break

        # Only transient exceptions reach this point. Never sleep after the last try.
        if attempt < max_attempts:
            logger.warning(
                "LLM retry scheduled: next_attempt=%d/%d delay_seconds=%.1f",
                attempt + 1, max_attempts, delay_seconds,
            )
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 8.0)

    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    logger.info(
        "LLM request finished: success=%s duration_ms=%.2f",
        response is not None,
        duration_ms
    )

    return response, duration_ms
