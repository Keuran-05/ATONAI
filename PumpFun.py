import re
import ssl
import aiohttp
import backoff
from bs4 import BeautifulSoup
from Dexscreener import get_website_link_DX, get_telegram_link_DX
from Logs import log_error, log_info, log_warning, log_debug

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Define the backoff decorator to handle retries
@backoff.on_exception(
    backoff.expo,
    aiohttp.ClientError,
    max_tries=5,
    giveup=lambda e: isinstance(e, aiohttp.ClientResponseError) and e.status != 429
)
async def make_request_with_backoff(url, return_type="text"):
    """Asynchronously make a GET request to the URL."""
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


    except aiohttp.ClientError as e:
        log_error(f"Error fetching URL {url}: {e}")
        return None


async def get_bonding_curve_address(token_address):
    url = f"https://pump.fun/coin/{token_address}"
    log_info(f"Fetching Bonding Curve from Pump.fun for token address: {token_address}")
    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        return None

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response, 'html.parser')
    scripts = soup.find_all("script")

    for script in scripts:
        script_content = str(script)
        if "associated_bonding_curve" in script_content:

            # Regex to match the address after "associated_bonding_curve"
            pattern = r'associated_bonding_curve\\":\\"([^\\"]+)\\"'
            # Search for the pattern
            match = re.search(pattern, script_content)

            if match:
                bonding_curve_address = match.group(1)
                log_info(f"Extracted Address: {bonding_curve_address}")
                return bonding_curve_address
            else:
                log_warning("No matching address found in the script content.")
    return None


async def get_image(token_address):
    """Scrape the image URI for a given token address."""
    log_info(f"Fetching image from Pump.fun for token address: {token_address}")
    url = f"https://pump.fun/coin/{token_address}"

    # Send a GET request to the URL
    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        return None

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response, 'html.parser')

    # Look for script tags containing image URI or similar data
    scripts = soup.find_all("script")

    for script in scripts:
        script_content = str(script)

        if "image_uri" in script_content:  # Check for the presence of image data
            log_info(f"Found script content with image_uri: {script_content}")

            # Regex to match the image URI
            pattern = r'image_uri\\":\\"([^\\"]+)\\"'  # Adjust based on actual structure
            match = re.search(pattern, script_content)

            if match:
                image_uri = match.group(1)  # Extract the image URI
                log_info(f"Extracted Image URI: {image_uri}")
                return image_uri
            else:
                log_warning("No matching image URI found in the script content.")
    return None


async def get_telegram_link_PF(token_address):
    url = f"https://pump.fun/coin/{token_address}"
    log_info(f"Fetching Telegram link from Pump.fun for token address: {token_address}")

    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        log_warning(f"Pump.fun returned an error or invalid data for {token_address}. Falling back to DexScreener.")
        return await get_telegram_link_DX(token_address)

    soup = BeautifulSoup(response, 'html.parser')
    script_tags = soup.find_all('script')

    if not script_tags:
        log_warning(f"No script tags found in the Pump.fun page for {token_address}.")
        return await get_telegram_link_DX(token_address)

    for script in script_tags:
        telegram_match = re.search(r'https://t\.me/[A-Za-z0-9_]+', str(script))
        if telegram_match:
            telegram_link = telegram_match.group(0).rstrip('\\')
            log_info(f"Telegram link found on Pump.fun: {telegram_link}")
            return telegram_link

    log_warning(f"No Telegram link found on Pump.fun for {token_address}. Falling back to DexScreener.")
    return await get_telegram_link_DX(token_address)


async def get_website_link_PF(token_address):
    url = f"https://pump.fun/coin/{token_address}"
    log_info(f"Fetching Website link from Pump.fun for token address: {token_address}")

    response = await make_request_with_backoff(url)

    if response == "Invalid token Address":
        return "Invalid token Address"

    if not response:
        log_warning(f"Pump.fun returned an error or invalid data for {token_address}. Falling back to DexScreener.")
        return await get_website_link_DX(token_address)

    soup = BeautifulSoup(response, 'html.parser')
    script_tags = soup.find_all('script')

    if not script_tags:
        log_warning(f"No script tags found in the Pump.fun page for {token_address}.")
        return await get_website_link_DX(token_address)

    for script in script_tags:
        if script.string:
            string = script.get_text()
            website_url = re.search(r'website\\":\\"(https://[^"]+)\\"', string)

            if website_url:
                log_info("Website link found on pump.fun")
                return website_url.group(1)

    log_warning("No website link found on pump.fun")
    return await get_website_link_DX(token_address)