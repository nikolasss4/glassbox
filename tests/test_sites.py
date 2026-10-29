"""Every mock page should load and run its scripts without throwing."""

import pytest
from playwright.async_api import Browser

from glassbox.sitesrv import SITES_DIR, SiteServer

PAGES = sorted(str(p.relative_to(SITES_DIR)) for p in SITES_DIR.rglob("*.html"))


@pytest.mark.parametrize("path", PAGES)
async def test_page_loads_without_js_errors(sites: SiteServer, browser: Browser, path: str) -> None:
    ctx = await browser.new_context()
    page = await ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # 2fa.html and new-password.html expect query/session state; they must still not throw.
    await page.goto(f"{sites.base_url}/sites/{path}?id=mug-blue&user=dave")
    await page.wait_for_timeout(100)
    await ctx.close()
    assert errors == []
