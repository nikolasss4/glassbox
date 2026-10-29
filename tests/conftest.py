from collections.abc import AsyncIterator, Iterator

import pytest
from playwright.async_api import Browser, async_playwright

from glassbox.sitesrv import SiteServer


@pytest.fixture(scope="session")
def sites() -> Iterator[SiteServer]:
    with SiteServer() as server:
        yield server


@pytest.fixture(scope="session")
async def browser() -> AsyncIterator[Browser]:
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        yield b
        await b.close()
