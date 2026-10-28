"""Testes de extração segura, manifesto e escolha do arquivo consolidado.

DADOS SINTÉTICOS: ZIPs e CSVs criados no próprio teste.
"""
import zipfile

import pytest

from src.aquisicao import manifesto
from src.aquisicao.extracao import ErroExtracao, extrair
from src.tratamento.leitura_tse import escolher_membro_consolidado
from src.validacao.auditoria import verificar_sobreposicao


def test_extracao_bloqueia_path_traversal(tmp_path):
    z = tmp_path / "mal.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../fora.txt", "x")
    with pytest.raises(ErroExtracao):
        extrair(z, tmp_path / "dest")
    assert not (tmp_path / "fora.txt").exists()


def test_extracao_reutiliza_e_filtra(tmp_path):
    z = tmp_path / "ok.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a_BRASIL.csv", "c1;c2\n1;2\n")
        zf.writestr("leiame.pdf", "pdf")
    [p] = extrair(z, tmp_path / "d", padrao="_BRASIL")
    assert p.read_text() == "c1;c2\n1;2\n"
    mtime = p.stat().st_mtime_ns
    extrair(z, tmp_path / "d", padrao="_BRASIL")
    assert p.stat().st_mtime_ns == mtime


def test_escolhe_brasil_e_rejeita_ambiguidade(tmp_path):
    z = tmp_path / "r.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for n in ("x_BR.csv", "x_AC.csv", "x_BRASIL.csv"):
            zf.writestr(n, "a\n")
    assert escolher_membro_consolidado(z) == "x_BRASIL.csv"

    z2 = tmp_path / "r2.zip"
    with zipfile.ZipFile(z2, "w") as zf:
        zf.writestr("x_AC.csv", "a\n")
        zf.writestr("x_AL.csv", "a\n")
    with pytest.raises(ValueError):
        escolher_membro_consolidado(z2)


def test_sobreposicao_brasil_igual_soma():
    r = verificar_sobreposicao({"x_BR.csv": 10, "x_AC.csv": 5, "x_BRASIL.csv": 15})
    assert r["brasil_e_soma"] is True
    r = verificar_sobreposicao({"x_BR.csv": 10, "x_AC.csv": 5, "x_BRASIL.csv": 14})
    assert r["brasil_e_soma"] is False


def test_manifesto_registra_e_mescla(tmp_path):
    arq = tmp_path / "m.json"
    manifesto.registrar("r", {"a": 1}, arq)
    manifesto.registrar("r", {"b": 2}, arq)
    assert manifesto.carregar(arq)["recursos"]["r"] == {"a": 1, "b": 2}


def test_sha256(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"abc")
    assert manifesto.sha256_arquivo(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
