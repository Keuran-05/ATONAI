from Logs import log_error, log_warning
from PumpFun import get_telegram_link_PF


async def get_telegram_link(token_address):
    link = await get_telegram_link_PF(token_address)
    return link


def extract_telegram_link(pair):
    if not isinstance(pair, dict):
        log_error(f"Invalid pair structure: {pair}")
        return None

    info = pair.get('info', {})
    if not isinstance(info, dict):
        log_warning(f"Invalid 'info' structure in pair: {pair}")
        return None

    socials = info.get('socials', [])
    if not isinstance(socials, list):
        log_warning(f"Invalid 'socials' structure in pair info: {info}")
        return None

    for social in socials:
        if social.get('type') == 'telegram':
            return social.get('url')
    return None

