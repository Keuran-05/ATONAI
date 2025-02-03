from PumpFun import get_website_link_PF


async def get_website_link(token_address):
    link = await get_website_link_PF(token_address)
    return link

