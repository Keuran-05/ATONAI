import asyncio
import ssl
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
import aiohttp
import backoff
from urllib.parse import urlencode
from Config import SOLSCAN_API_KEY
from Logs import log_debug, log_warning, log_error

# Create SSL context once at module level
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Constants
BASE_URL = "https://pro-api.solscan.io/v2.0"
HEADERS = {'token': SOLSCAN_API_KEY}
MAX_RETRIES = 3
TIMEOUT = aiohttp.ClientTimeout(total=30)

# Shared session for connection pooling
session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    """Get or create shared aiohttp session."""
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                ssl=ssl_context,
                limit=100,  # Connection pool limit
                ttl_dns_cache=300,  # DNS cache TTL
                keepalive_timeout=60
            ),
            timeout=TIMEOUT,
            headers=HEADERS
        )
    return session


async def close_session() -> None:
    """Close the shared session."""
    global session
    if session and not session.closed:
        await session.close()
        session = None


@backoff.on_exception(
    backoff.expo,
    (aiohttp.ClientResponseError, aiohttp.ClientError, asyncio.TimeoutError),
    max_tries=MAX_RETRIES,
    max_time=10,
    jitter=backoff.full_jitter,
    raise_on_giveup=False
)
async def make_request_with_backoff(url: str) -> Optional[Dict]:
    """Make HTTP request with exponential backoff and retries."""
    try:
        session = await get_session()
        log_debug(f"Making GET request to {url}")

        async with session.get(url) as response:
            status = response.status
            log_debug(f"Response Status Code: {status}")

            if status in {429, 503}:
                retry_after = min(
                    int(response.headers.get("retry-after", 5)),
                    60  # Cap maximum retry delay
                )
                log_warning(f"Rate limited. Retrying after {retry_after} seconds...")
                await asyncio.sleep(retry_after)
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=status
                )

            if status != 200:
                log_error(f"Unexpected status code {status} for {url}")
                response.raise_for_status()

            return await response.json()

    except asyncio.TimeoutError:
        log_error(f"Request timed out for {url}")
        return None
    except aiohttp.ClientError as e:
        log_error(f"Client error for {url}: {str(e)}")
        return None
    except Exception as e:
        log_error(f"Unexpected error for {url}: {str(e)}")
        return None


def format_date(timestamp: int) -> str:
    """Format timestamp to required date string."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y%m%d')


async def get_price(address: str, time: int) -> Optional[List[Dict[str, Union[str, float]]]]:
    """
    Get token price for a specific address and time.

    Args:
        address: Token address
        time: Unix timestamp

    Returns:
        List of price data or None if request fails
    """
    try:
        params = {
            'address': address,
            'time[]': format_date(time)
        }

        url = f"{BASE_URL}/token/price?{urlencode(params, doseq=True)}"
        data = await make_request_with_backoff(url)

        if not data:
            log_error("No response received for price.")
            return None

        if "error" in data:
            error_msg = data['error'].get('message', 'Unknown error')
            log_error(f"Error in price response: {error_msg}")
            return None

        response_data = data.get('data')
        if response_data:
            log_debug(f"Price retrieved: {response_data}")
            return response_data

        log_error("No data found in the response.")
        return None

    except Exception as e:
        log_error(f"Failed to get price: {str(e)}")
        return None

    finally:
        # Optionally close session if needed
        # await close_session()
        pass


# Cleanup function to be called when shutting down
async def cleanup():
    """Cleanup function to close the session when shutting down."""
    await close_session()