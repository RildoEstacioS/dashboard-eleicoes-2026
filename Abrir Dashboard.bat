@echo off
rem ==========================================================================
rem  Dashboard Eleicoes 2026 - inicializador de um clique (Windows)
rem  Duplo clique: prepara o que faltar e abre o painel no navegador.
rem  Para encerrar o painel, feche esta janela.
rem ==========================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Dashboard Eleicoes 2026

set "PY=.venv\Scripts\python.exe"

rem ---- 1. Ambiente Python (so na primeira vez) ------------------------------
if not exist "%PY%" (
    echo.
    echo  Primeira execucao: criando o ambiente Python e instalando dependencias.
    echo  Isso pode levar alguns minutos.
    echo.
    where py >nul 2>nul
    if errorlevel 1 (
        echo  [ERRO] Python nao encontrado. Instale o Python 3.11 em https://www.python.org/downloads/
        echo         marcando a opcao "Add python.exe to PATH", e rode este arquivo de novo.
        pause
        exit /b 1
    )
    py -3.11 -m venv .venv || py -3 -m venv .venv
    if not exist "%PY%" (
        echo  [ERRO] Nao foi possivel criar o ambiente virtual .venv
        pause
        exit /b 1
    )
    "%PY%" -m pip install --upgrade pip -q
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo  [ERRO] Falha ao instalar as dependencias. Veja as mensagens acima.
        pause
        exit /b 1
    )
)

rem ---- 2. Dados oficiais (so na primeira vez) -------------------------------
if not exist "data\processed\modelo\disponibilidade.parquet" (
    echo.
    echo  Os dados oficiais ainda nao foram preparados.
    echo  O preparo baixa cerca de 690 MB do TSE e do IBGE e leva de 10 a 20 minutos.
    echo.
    choice /c SN /m "Deseja preparar os dados agora"
    if errorlevel 2 (
        echo  Ok. Rode este arquivo novamente quando quiser preparar os dados.
        pause
        exit /b 0
    )
    "%PY%" -m scripts.preparar_dados baixar || goto erro_dados
    "%PY%" -m scripts.preparar_dados auditar || goto erro_dados
    "%PY%" -m scripts.preparar_dados geografia || goto erro_dados
    "%PY%" -m scripts.preparar_dados modelar || goto erro_dados
)
if not exist "static\geo\ufs.geojson" (
    rem As malhas publicadas para o navegador podem faltar (ex.: pasta copiada sem static/geo).
    "%PY%" -c "from src.geografia.preparar import publicar_web; publicar_web()" || goto erro_dados
)

rem ---- 3. Abrir o painel ----------------------------------------------------
echo.
echo  Abrindo o Dashboard Eleicoes 2026 no navegador...
echo  (para encerrar, feche esta janela)
echo.
"%PY%" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
exit /b 0

:erro_dados
echo.
echo  [ERRO] O preparo dos dados falhou. Veja as mensagens acima e tente novamente.
echo         Arquivos ja baixados sao reaproveitados na proxima tentativa.
pause
exit /b 1
