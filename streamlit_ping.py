import asyncio
import json
import os
from datetime import datetime, timezone

import aiohttp

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

SLEEP_MARKERS = [
    "Yes, get this app back up!",
    "This app has gone to sleep",
    "app has gone to sleep",
    "Zzzz",
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

TIMEOUT_SECONDS = 30

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
LOG_TABLE = "streamlit_ping_log"


def _slug(url: str) -> str:
    return url.split("//")[1].split(".streamlit")[0]


async def ping(session: aiohttp.ClientSession, url: str) -> dict:
    slug = _slug(url)
    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
            body = await resp.text()
            sleeping = any(m in body for m in SLEEP_MARKERS)
            return {
                "url": url,
                "slug": slug,
                "http_status": resp.status,
                "sleeping": sleeping,
                "ok": resp.status < 400,
                "error": None,
            }
    except Exception as exc:
        return {
            "url": url,
            "slug": slug,
            "http_status": None,
            "sleeping": None,
            "ok": False,
            "error": str(exc),
        }


async def ping_all() -> list[dict]:
    async with aiohttp.ClientSession(headers=REQUEST_HEADERS) as session:
        tasks = [ping(session, url) for url in STREAMLIT_APPS]
        return await asyncio.gather(*tasks)


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
            detail = f"HTTP {r['http_status']} — ping sent, app will resume"
        else:
            state = "OK   "
            detail = f"HTTP {r['http_status']}"
        print(f"  [{state}]  {r['slug']:<60}  {detail}")

    ok = sum(1 for r in results if r["ok"])
    sleeping = sum(1 for r in results if r.get("sleeping"))
    errors = sum(1 for r in results if r.get("error"))
    print(f"\n  Total: {len(results)}  |  OK: {ok}  |  Sleeping: {sleeping}  |  Errors: {errors}\n")

    await log_to_supabase(results)


if __name__ == "__main__":
    asyncio.run(run())
