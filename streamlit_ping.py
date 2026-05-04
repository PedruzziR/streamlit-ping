import asyncio
import json
import os
from datetime import datetime, timezone

import aiohttp
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

STREAMLIT_APPS = [
    "https://neuropsicologabrunaligoskiifp2.streamlit.app/",
    "https://neuropsicologabrunaligoski-aivd-familiar.streamlit.app/",
    "https://neuropsicologabrunaligoski-aivd-paciente.streamlit.app/",
    "https://neuropsicologabrunaligoskietdahad.streamlit.app/",
    "https://neuropsicologabrunaligoskietdahcriad.streamlit.app/",
    "https://neuropsicologabrunaligoskietdahpais.streamlit.app/",
    "https://neuropsicologabrunaligoski-gai.streamlit.app/",
    "https://neuropsicologabrunaligoski-gds-15.streamlit.app/",
    "https://neuropsicologabrunaligoski-qedp.streamlit.app/",
    "https://neuropsicologabrunaligoskisnapiv.streamlit.app/",
    "https://neuropsicologabrunaligoskisrsautorrelato.streamlit.app/",
    "https://neuropsicologabrunaligoskisrsheterorrelato.streamlit.app/",
    "https://neuropsicologabrunaligoskisrsescolar.streamlit.app/",
    "https://neuropsicologabrunaligoskisrspreescolar.streamlit.app/",
    "https://neuropsicologabrunaligoskifdt.streamlit.app/",
    "https://neuropsicologabrunaligoski-indicekatz.streamlit.app/",
    "https://paineldecontroleavaliacoesneuropsicologicas.streamlit.app/",
    "https://neuropsicologa-bruna-ligoski-formulario-inicial-adulto.streamlit.app/",
    "https://neuropsicologa-bruna-ligoski-formulario-inicial-infantil.streamlit.app/",
]

SLEEP_BUTTON_TEXT = "Yes, get this app back up!"
KEEPALIVE_BUTTON_TEXT = "Manter ativo"

PAGE_LOAD_WAIT_MS = 12_000   # aguarda React renderizar (mesmo princípio dos 15s do bot desktop)
CONCURRENCY = 5              # páginas abertas em paralelo
NAV_TIMEOUT_MS = 35_000

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
LOG_TABLE = "streamlit_ping_log"


def _slug(url: str) -> str:
    return url.split("//")[1].split(".streamlit")[0]


async def visit_app(page, url: str) -> dict:
    slug = _slug(url)
    try:
        await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        await page.wait_for_timeout(PAGE_LOAD_WAIT_MS)

        sleeping = False
        sleep_btn = page.get_by_text(SLEEP_BUTTON_TEXT, exact=False)
        if await sleep_btn.count() > 0:
            await sleep_btn.first.click()
            sleeping = True

        if not sleeping:
            keepalive_btn = page.get_by_text(KEEPALIVE_BUTTON_TEXT, exact=False)
            if await keepalive_btn.count() > 0:
                await keepalive_btn.first.click()

        return {
            "url": url,
            "slug": slug,
            "sleeping": sleeping,
            "ok": True,
            "error": None,
            "http_status": 200,
        }
    except PlaywrightTimeout:
        return {
            "url": url,
            "slug": slug,
            "sleeping": None,
            "ok": False,
            "error": "Timeout",
            "http_status": None,
        }
    except Exception as exc:
        return {
            "url": url,
            "slug": slug,
            "sleeping": None,
            "ok": False,
            "error": str(exc),
            "http_status": None,
        }


async def ping_all() -> list[dict]:
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )

        async def run_one(url: str) -> dict:
            async with semaphore:
                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                try:
                    return await visit_app(page, url)
                finally:
                    await page.close()

        tasks = [run_one(url) for url in STREAMLIT_APPS]
        results = await asyncio.gather(*tasks)
        await browser.close()
        return list(results)


async def log_to_supabase(results: list[dict]) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[supabase] Credentials not configured — skipping log.")
        return

    payload = {
        "pinged_at": datetime.now(timezone.utc).isoformat(),
        "total_apps": len(results),
        "ok_count": sum(1 for r in results if r["ok"]),
        "sleeping_count": sum(1 for r in results if r.get("sleeping")),
        "error_count": sum(1 for r in results if r.get("error")),
        "details": json.dumps(results),
    }

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SUPABASE_URL}/rest/v1/{LOG_TABLE}",
            json=payload,
            headers=headers,
            timeout=timeout,
        ) as resp:
            if resp.status not in (200, 201):
                body = await resp.text()
                print(f"[supabase] Log failed: HTTP {resp.status} — {body}")
            else:
                print("[supabase] Log saved.")


async def run() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== streamlit_ping | {now} | {len(STREAMLIT_APPS)} apps ===\n")

    results = await ping_all()

    for r in sorted(results, key=lambda x: x["slug"]):
        if r["error"]:
            state = "ERROR"
            detail = r["error"]
        elif r["sleeping"]:
            state = "SLEEP"
            detail = "botão clicado — app retomando"
        else:
            state = "OK   "
            detail = "online"
        print(f"  [{state}]  {r['slug']:<60}  {detail}")

    ok = sum(1 for r in results if r["ok"])
    sleeping = sum(1 for r in results if r.get("sleeping"))
    errors = sum(1 for r in results if r.get("error"))
    print(f"\n  Total: {len(results)}  |  OK: {ok}  |  Dormindo: {sleeping}  |  Erros: {errors}\n")

    await log_to_supabase(results)


if __name__ == "__main__":
    asyncio.run(run())
