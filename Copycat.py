import asyncio
from io import BytesIO
import aiohttp
import numpy as np
from PIL import Image, UnidentifiedImageError
from Dexscreener import check_token_exists
from Helius import getAsset
from Logs import log_error, log_info
from PumpFun import get_image


def calculate_checksum(image):
    """Calculate the checksum for an image."""
    if image.mode != 'RGB':
        image = image.convert('RGB')
    byte_stream = BytesIO()
    image.save(byte_stream, format='JPEG')
    checksum = hash(byte_stream.getvalue())
    return checksum


async def compare_histograms(image1, image2):
    """Asynchronously compare histograms of two images."""
    hist1 = await asyncio.get_event_loop().run_in_executor(None, image1.histogram)
    hist2 = await asyncio.get_event_loop().run_in_executor(None, image2.histogram)
    correlation = sum((h1 - h2) ** 2 for h1, h2 in zip(hist1, hist2))
    return 1.0 - correlation / float(len(hist1))


async def compare_pixels(image1, image2):
    """Asynchronously compare two images pixel-by-pixel."""
    img1_array = np.array(image1)
    img2_array = np.array(image2)
    return img1_array.shape == img2_array.shape and np.array_equal(img1_array, img2_array)


# Image comparison
async def download_image_to_memory(img_url, retry_attempts=3):
    """Download an image to memory with retries."""
    for _ in range(retry_attempts):
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.get(img_url) as response:
                    if response.status == 200:
                        return BytesIO(await response.read())
        except Exception as e:
            log_error(f"Error downloading image: {e}")
    return None

async def is_CopyCat(given_data, found_image_url):
    """Perform copycat analysis asynchronously for two images."""
    try:
        # Step 1: Download found images
        found_data = await download_image_to_memory(found_image_url)

        if not given_data or not found_data:
            log_error("Failed to download one or both images.")
            return False

        # Step 2: Open images using a thread-safe executor
        loop = asyncio.get_event_loop()
        try:
            given_image = await loop.run_in_executor(None, Image.open, given_data)
            found_image = await loop.run_in_executor(None, Image.open, found_data)
        except UnidentifiedImageError as e:
            log_error(f"Invalid image data: {e}")
            return False

        # Step 3: Ensure consistent image modes
        if given_image.mode != "RGBA":
            given_image = await loop.run_in_executor(None, given_image.convert, "RGBA")
        if found_image.mode != "RGBA":
            found_image = await loop.run_in_executor(None, found_image.convert, "RGBA")

        # Step 4: Perform comparison
        with given_image, found_image:
            # Compare checksums
            if calculate_checksum(given_image) == calculate_checksum(found_image):
                log_info(f"Images are identical based on checksum. Image: {found_image_url}")
                return True

            # Skip histogram comparison if pixel comparison is more accurate
            are_pixels_similar = await compare_pixels(given_image, found_image)
            if are_pixels_similar:
                log_info(f"Images are identical based on pixel comparison. Image: {found_image_url}")
                return True

            # Compare histograms as a last resort
            if await compare_histograms(given_image, found_image) == 1.0:
                log_info(f"Images are identical based on histogram comparison. Image: {found_image_url}")
                return True

        return False

    except Exception as e:
        log_error(f"Error in is_CopyCat: {e}")
        return False


# Main copycat analysis
async def run_copycat(token_address):
    """Run the copycat analysis for a given token address."""
    log_info(f"Starting copycat analysis for token address: {token_address}")

    try:
        data = await getAsset(token_address)
        result = data.get("result", {}).get("content", {}).get("metadata", {})
        symbol = result.get("symbol", "Symbol not found")
        name = result.get("name", "Name not found")
        given_image_url = data.get("result", {}).get("content", {}).get("links", {}).get("image", None)
    except Exception as e:
        return None

    if not symbol or symbol == "Symbol not found":
        return "❌ Token symbol not found."
    if not given_image_url:
        return "❌ Token image not available."

    all_addresses = await check_token_exists(symbol, name, token_address)
    if not all_addresses:
        return "🔴 (COIN IS UNIQUE)"

    images = await asyncio.gather(*(get_image(address) for address in all_addresses), return_exceptions=True)
    valid_images = [(address, img) for address, img in zip(all_addresses, images) if img]
    given_data = await download_image_to_memory(given_image_url)

    results = await asyncio.gather(
        *(is_CopyCat(given_data, img) for _, img in valid_images)
    )

    for (address, _), result in zip(valid_images, results):
        if result:
            return f"🟢 (COIN ALREADY EXISTS)"
    return "🔴 (COIN IS UNIQUE)"

