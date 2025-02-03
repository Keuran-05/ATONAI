import ssl
import aiohttp
import backoff
from Logs import log_info, log_warning, log_debug, log_error


@backoff.on_exception(
    backoff.expo,
    aiohttp.ClientError,
    max_tries=5,
    giveup=lambda e: isinstance(e, aiohttp.ClientResponseError) and e.status != 429
)
async def make_request_with_backoff(url, return_type="json"):
    """Asynchronously make a GET request to the URL."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:  # Session is created here
            async with session.get(url) as response:
                log_debug(f"Response Status Code for {url}: {response.status}")
                if response.status == 200:
                    return await response.json() if return_type == "json" else await response.text()
                elif response.status == 404:
                    log_error(f"Invalid Contract Address (404) for URL: {url}")
                    return "Invalid token Address"
                elif response.status == 429:
                    log_warning("Rate limit exceeded. Retrying...")
                    raise aiohttp.ClientResponseError(
                        response.request_info, response.history, status=response.status
                    )

                log_warning(f"Unexpected status code {response.status} for URL: {url}")
                raise aiohttp.ClientResponseError(
                    response.request_info, response.history, status=response.status
                )
                return None

    except aiohttp.ClientError as e:
        log_error(f"Error fetching URL {url}: {e}")
        return None


async def get_telegram_link_DX(token_address):
    from Telegram import extract_telegram_link
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    log_info(f"Fetching Telegram link from Dexscreener for token address: {token_address}")
    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        log_warning(f"Dexscreener returned an error or invalid data for {token_address}.")
        return None

    if response and "pairs" in response and isinstance(response.get("pairs", []), list):
        for pair in response.get("pairs", []):
            if pair.get('dexId') == 'raydium':
                telegram_link = extract_telegram_link(pair)
                if telegram_link:
                    log_info(f"Telegram link found on Raydium: {telegram_link}")
                    return telegram_link

        for pair in response.get("pairs", []):
            telegram_link = extract_telegram_link(pair)
            if telegram_link:
                log_info(f"Telegram link found on alternative exchange: {telegram_link}")
                return telegram_link

    log_warning(f"No Telegram link found in DexScreener data for {token_address}.")
    return "No Telegram link found."


async def get_website_link_DX(token_address):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    log_info(f"Fetching website link from Dexscreener for token address: {token_address}")
    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        log_warning(f"Dexscreener returned an error or invalid data for {token_address}.")
        return None

    if response and "pairs" in response and isinstance(response.get("pairs", []), list):
        for pair in response.get("pairs", []):
            info = pair.get("info", {})
            websites = info.get("websites", [])
            for website in websites:
                if website.get("label", "") == "Website":
                    website_link = website.get("url", "")
                    if website_link:
                        log_info(f"Website link found in DexScreener for {token_address}.")

                        return website_link

    log_warning(f"No Website link found in DexScreener data for {token_address}.")
    return "No Website link found."


async def check_token_exists(token_symbol, token_name, token_address):
    """Asynchronously check if a token exists on the Solana network."""
    log_info(f"Checking token existence for symbol: {token_symbol}, name: {token_name}")
    url = f"https://api.dexscreener.com/latest/dex/search?q={token_symbol}/SOL"

    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        log_warning(f"Dexscreener returned an error or invalid data for {token_symbol}.")
        return None

    pairs = response.get("pairs", [])
    return {
        pair["baseToken"]["address"]
        for pair in pairs if pair.get("chainId") == "solana" and "baseToken" in pair and pair["baseToken"]["address"] != token_address
    }
    return set()


async def get_all_volumes_DX(token_address):
    from Volume import format_trading_volumes
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    log_info(f"Fetching trading volumes for token address: {token_address}")

    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        log_warning(f"Dexscreener returned an error or invalid data for {token_address}.")
        return None

    # Check if "pairs" is None
    pairs = response.get("pairs", None)
    if pairs is None:
        log_info("Invalid token Address")
        return "Invalid token Address"

    if not response or "pairs" not in response:
        log_warning("Response does not contain 'pairs'.")
        return "Volume data not found."

    # Check for Raydium exchange first
    for pair in response.get("pairs", []):
        if pair.get("dexId") == "raydium":  # Adjust DEX ID as needed
            volumes = pair.get("volume", {})
            if volumes:
                log_info("Volume data found on Raydium.")
                return await format_trading_volumes(volumes)

    # Fallback to the first available exchange
    for pair in response.get("pairs", []):
        volumes = pair.get("volume", {})
        if volumes:
            log_info("Volume data found on an alternative exchange.")
            return await format_trading_volumes(volumes)

    log_warning("Volume data not found.")
    return "Volume data not found."


