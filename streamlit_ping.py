import asyncio
import json
import os
import time
from datetime import datetime, timezone

import aiohttp
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ================= URLS DOS APPS =================
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
    "https://psicologabrunaligoski.streamlit.app/",
    "https://neuropsicologa-bruna-ligoski-escalaansiedadeinfantil.streamlit.app/",
    "https://neuropsicologa-brunaligoski-bdi.streamlit.app/",
    "https://neuropsicologa-brunaligoski-bai.streamlit.app/",
    "https://psicologabrunaligoski-anamneseinformante.streamlit.app/",
]

# URL deste próprio app após deploy — preencher em Settings > Variables > PING_APP_URL
PING_APP_URL = os.environ.get("PING_APP_URL", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
LOG_TABLE = "streamlit_ping_log"
# ==================================================


def _slug(url: str) -> str:
    return url.split("//")[1].split(".streamlit")[0]


def _make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)  # Selenium Manager resolve o driver automaticamente


def run_bot() -> list[dict]:
    all_urls = list(STREAMLIT_APPS)
    if PING_APP_URL:
        all_urls.append(PING_APP_URL)

    results = []
    driver = _make_driver()

    try:
        for url in all_urls:
            slug = _slug(url)
            try:
                driver.get(url)
                time.sleep(15)  # aguarda React renderizar (igual ao bot desktop)

                # Acorda o app se estiver dormindo
                sleep_btns = driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'Yes, get this app back up!')]"
                )
                if sleep_btns:
                    driver.execute_script("arguments[0].click();", sleep_btns[0])
                    print(f"  [SLEEP]  {slug:<60}  botão clicado — app retomando")
                    results.append({"url": url, "slug": slug, "sleeping": True, "ok": True, "error": None})
                else:
                    # Se for o próprio app de ping, clica em "Manter ativo" (loop eterno)
                    if url == PING_APP_URL:
                        keepalive_btns = driver.find_elements(
                            By.XPATH, "//*[contains(text(), 'Manter ativo')]"
                        )
                        if keepalive_btns:
                            driver.execute_script("arguments[0].click();", keepalive_btns[0])
                    print(f"  [OK   ]  {slug:<60}  online")
                    results.append({"url": url, "slug": slug, "sleeping": False, "ok": True, "error": None})

            except Exception as exc:
                print(f"  [ERROR]  {slug:<60}  {exc}")
                results.append({"url": url, "slug": slug, "sleeping": None, "ok": False, "error": str(exc)})
    finally:
        driver.quit()

    return results


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


def main() -> None:
    all_urls = STREAMLIT_APPS + ([PING_APP_URL] if PING_APP_URL else [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== streamlit_ping | {now} | {len(all_urls)} apps ===\n")

    results = run_bot()

    ok = sum(1 for r in results if r["ok"])
    sleeping = sum(1 for r in results if r.get("sleeping"))
    errors = sum(1 for r in results if r.get("error"))
    print(f"\n  Total: {len(results)}  |  OK: {ok}  |  Dormindo: {sleeping}  |  Erros: {errors}\n")

    asyncio.run(log_to_supabase(results))


# ─── Detecta se está rodando dentro do Streamlit Community Cloud ─────────────
def _in_streamlit() -> bool:
    try:
        import streamlit as st
        return st.runtime.exists()
    except Exception:
        return False


if _in_streamlit():
    # Modo Streamlit: exibe apenas a UI, NÃO executa o bot (Chrome não existe aqui)
    import streamlit as st
    st.set_page_config(page_title="Ping Monitor", page_icon="🏓")
    st.title("Monitor de Apps")
    st.caption("Mantido ativo pelo robô de ping a cada 15 minutos.")
    if st.button("Manter ativo", key="keepalive", type="primary", use_container_width=True):
        st.success("Ping recebido — app ativo!")
    else:
        st.info("Aguardando próximo ping...")

elif __name__ == "__main__":
    # Modo GitHub Actions: executa o bot Selenium normalmente
    main()
