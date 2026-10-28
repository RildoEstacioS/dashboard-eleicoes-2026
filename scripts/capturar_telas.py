"""Captura as telas do painel para o README (docs/imagens/).

Sobe o app com `streamlit run` numa porta própria, abre o Microsoft Edge (ou o
Chrome) em modo headless e o controla pelo DevTools Protocol, usando o pacote
`websockets`, que já vem com o Streamlit. Nada é instalado.

Uso (com os dados já preparados):
    python -m scripts.capturar_telas
"""
from __future__ import annotations

import base64
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import warnings

from websockets.sync.client import connect

warnings.filterwarnings("ignore", category=DeprecationWarning, module=__name__)

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "imagens"
PORTA_APP, PORTA_CDP = 8597, 9337
LARGURA, ALTURA = 1600, 1000
NAVEGADORES = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def _esperar_http(url: str, limite: float = 90) -> str:
    fim = time.time() + limite
    while time.time() < fim:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.read().decode()
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(url)


class Pagina:
    """Cliente mínimo do DevTools Protocol para uma aba."""

    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=None)
        self._ids = itertools.count(1)

    def cmd(self, metodo: str, **params):
        i = next(self._ids)
        self.ws.send(json.dumps({"id": i, "method": metodo, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == i:
                if "error" in m:
                    raise RuntimeError(f"{metodo}: {m['error']}")
                return m.get("result", {})

    def js(self, expr: str):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"])
        return r["result"].get("value")

    def esperar(self, cond: str, limite: float = 60) -> None:
        fim = time.time() + limite
        while time.time() < fim:
            if self.js(cond):
                return
            time.sleep(0.3)
        raise TimeoutError(cond)

    def ocioso(self, extra: float = 3.0) -> None:
        """Espera o Streamlit terminar o rerun e os mapas desenharem."""
        time.sleep(0.8)
        estavel = 0
        fim = time.time() + 90
        while estavel < 4 and time.time() < fim:
            rodando = self.js("!!document.querySelector('[data-testid=\"stStatusWidget\"]') || "
                              "!!document.querySelector('[data-testid=\"stSkeleton\"]')")
            estavel = 0 if rodando else estavel + 1
            time.sleep(0.4)
        time.sleep(extra)

    def clicar_xy(self, x: float, y: float) -> None:
        for tipo in ("mousePressed", "mouseReleased"):
            self.cmd("Input.dispatchMouseEvent", type=tipo, x=x, y=y, button="left", clickCount=1)

    def clicar(self, seletor_js: str) -> None:
        """Clica no centro do elemento devolvido pela expressão JS."""
        r = self.js(f"(() => {{ const e = {seletor_js}; if (!e) return null; e.scrollIntoView({{block:'center'}});"
                    "const b = e.getBoundingClientRect(); return [b.x + b.width/2, b.y + b.height/2]; })()")
        if r is None:
            raise LookupError(seletor_js)
        self.clicar_xy(*r)

    def tecla(self, nome: str, codigo: int) -> None:
        for tipo in ("keyDown", "keyUp"):
            self.cmd("Input.dispatchKeyEvent", type=tipo, key=nome, code=nome, windowsVirtualKeyCode=codigo)

    # ---- widgets do Streamlit ------------------------------------------------
    @staticmethod
    def _por_rotulo(testid: str, rotulo: str) -> str:
        return (f"[...document.querySelectorAll('[data-testid=\"{testid}\"]')]"
                f".find(w => w.innerText.trim().startsWith({json.dumps(rotulo)}))")

    def escolher(self, rotulo: str, opcao: str) -> None:
        """Seleciona `opcao` no selectbox cujo rótulo começa com `rotulo`."""
        self.clicar(f"{self._por_rotulo('stSelectbox', rotulo)}?.querySelector('[role=\"combobox\"], input')")
        time.sleep(0.4)
        self.cmd("Input.insertText", text=opcao)
        time.sleep(0.6)
        self.tecla("Enter", 13)
        self.ocioso(1.0)

    def opcao(self, texto: str, dentro: str = "document") -> None:
        """Clica na opção de rádio (ou segmento) com o texto exato."""
        self.clicar(f"[...{dentro}.querySelectorAll('label, button')]"
                    f".find(e => e.innerText.trim() === {json.dumps(texto)})")
        self.ocioso(1.0)

    def aba(self, texto: str) -> None:
        self.clicar(f"[...document.querySelectorAll('button[role=\"tab\"]')]"
                    f".find(e => e.innerText.trim().startsWith({json.dumps(texto)}))")
        self.ocioso(1.5)

    def pagina(self, titulo: str) -> None:
        """Troca de página pela navegação lateral (mantém a sessão e os filtros)."""
        self.clicar(f"[...document.querySelectorAll('[data-testid=\"stSidebarNav\"] a')]"
                    f".find(a => a.innerText.trim().endsWith({json.dumps(titulo)}))")
        self.ocioso()

    def topo(self) -> None:
        self.js("for (const s of ['[data-testid=\"stMain\"]', '[data-testid=\"stSidebarContent\"]',"
                " '[data-testid=\"stSidebarUserContent\"]']) document.querySelector(s)?.scrollTo(0, 0);"
                " window.scrollTo(0, 0)")
        time.sleep(0.5)

    def capturar(self, nome: str) -> Path:
        self.topo()
        png = base64.b64decode(self.cmd("Page.captureScreenshot", format="png")["data"])
        destino = SAIDA / f"{nome}.png"
        destino.write_bytes(png)
        print(f"  {destino.relative_to(RAIZ)}  ({len(png) / 1024:.0f} KB)")
        return destino


def roteiro(p: Pagina) -> None:
    p.capturar("01_visao_geral_presidente")

    p.opcao("2º turno")
    p.opcao("Brasil por município")
    p.capturar("02_presidente_2turno_municipios")

    p.pagina("1º × 2º turno")
    p.capturar("03_primeiro_x_segundo_turno")

    p.pagina("Participação")
    p.capturar("04_participacao")

    p.pagina("Visão geral")
    p.escolher("Cargo", "Governador")
    p.opcao("1º turno")
    p.opcao("Brasil por UF")
    p.capturar("05_governador_brasil")

    p.escolher("Cargo", "Deputado Federal")
    p.escolher("UF", "SP")
    p.opcao("Municípios de uma UF")
    p.capturar("06_deputado_federal_sp")

    p.escolher("Cargo", "Presidente")
    p.opcao("Brasil por UF")
    p.escolher("UF", "Exterior")
    p.capturar("07_votos_no_exterior")

    p.pagina("Dados e metodologia")
    p.capturar("08_dados_e_metodologia")


def main() -> int:
    exe = next((n for n in NAVEGADORES if Path(n).exists()), None)
    if exe is None:
        print("Microsoft Edge ou Google Chrome não encontrado.")
        return 1
    SAIDA.mkdir(parents=True, exist_ok=True)
    perfil = Path(tempfile.mkdtemp(prefix="captura_"))
    app = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
                            "--server.port", str(PORTA_APP), "--browser.gatherUsageStats", "false"],
                           cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    nav = None
    try:
        _esperar_http(f"http://localhost:{PORTA_APP}/_stcore/health")
        nav = subprocess.Popen([exe, "--headless=new", f"--remote-debugging-port={PORTA_CDP}",
                                f"--user-data-dir={perfil}", f"--window-size={LARGURA},{ALTURA}",
                                "--hide-scrollbars", "--force-device-scale-factor=1", "--lang=pt-BR",
                                "--no-first-run", "about:blank"])
        abas = json.loads(_esperar_http(f"http://127.0.0.1:{PORTA_CDP}/json"))
        p = Pagina(next(a for a in abas if a["type"] == "page")["webSocketDebuggerUrl"])
        p.cmd("Page.enable")
        p.cmd("Emulation.setDeviceMetricsOverride", width=LARGURA, height=ALTURA, deviceScaleFactor=1, mobile=False)
        p.cmd("Page.navigate", url=f"http://localhost:{PORTA_APP}/")
        p.esperar("!!document.querySelector('.js-plotly-plot')", limite=120)
        p.ocioso(4.0)
        print("Capturando telas:")
        roteiro(p)
    finally:
        if nav:
            nav.terminate()
        app.terminate()
        time.sleep(1)
        shutil.rmtree(perfil, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
