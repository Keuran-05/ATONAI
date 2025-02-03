from Dexscreener import get_all_volumes_DX
from Logs import log_info


async def get_all_volumes(token_address):
    volumes = await get_all_volumes_DX(token_address)
    return volumes

async def format_number(num):
    if num < 1000:
        return str(num)
    elif num < 1_000_000:
        return f"{num / 1_000:.2f}K".rstrip('0').rstrip('.')
    elif num < 1_000_000_000:
        return f"{num / 1_000_000:.2f}M".rstrip('0').rstrip('.')
    elif num < 1_000_000_000_000:
        return f"{num / 1_000_000_000:.2f}B".rstrip('0').rstrip('.')
    else:
        return f"{num / 1_000_000_000_000:.2f}T".rstrip('0').rstrip('.')


async def format_trading_volumes(volumes):
    """Format and display trading volumes based on specific conditions."""

    vol_24hr = await format_number(volumes.get('h24', 0))
    vol_6hr = await format_number(volumes.get('h6', 0))
    vol_1hr = await format_number(volumes.get('h1', 0))
    vol_5min = await format_number(volumes.get('m5', 0))

    log_info("Formatted volume data.")

    return f"Here's the trading volume for the token:\n" \
           f"- 24-hour volume: {vol_24hr}\n" \
           f"- 6-hour volume: {vol_6hr}\n" \
           f"- 1-hour volume: {vol_1hr}\n" \
           f"- 5-minute volume: {vol_5min}\n"

