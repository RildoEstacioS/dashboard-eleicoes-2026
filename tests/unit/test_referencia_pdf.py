"""Parser do Relatório de Totalização.

DADOS SINTÉTICOS: o texto abaixo imita o leiaute do PDF oficial, mas nomes,
números e votos são fictícios.
"""
from src.validacao.referencia_totalizacao import analisar_texto

TEXTO = """
Resumo Geral da Circunscrição - UF FICTÍCIA
2.2 Eleitorado apto a votar 1.000.000
2.4 Abstenção   20,00% 200.000
Votos válidos 100,00% 700.000
Votos válidos (nominais + legenda) 99,50% 650.000
Anexo III - Destinação de votos de candidatas e candidatos
Cargo: Governador
99 - FULANO FICTICIO Deferido Deferido Deferido EleitoVálido
Anexo IX - Resultado de votação
Cargo: Governador
400.000 57,14% 2º turno*99 - FULANO FICTICIO Válido
VICE FICTICIO
300.000 42,86% Não eleito88 - BELTRANO FICTICIO Válido
Cargo: Deputado Federal Vagas: 3 Vagas preenchidas por QP: 2
50.000 Eleito por QP*9999 - CICRANO FICTICIO Válido
1.234 1º Suplente8888 - OUTRO FICTICIO Válido
77 Não eleito7777 - ANULADO FICTICIO Anulado sub judice
Anexo X - Resultado de votação por partido/federação/coligação
Cargo: Deputado Federal
999.999 Eleito por QP*1111 - NAO DEVE SER LIDO Válido
Resultado de votação
Cargo: Presidente
10.000 60,00%12 - SECAO POR UF COLADA Válido
Cargo: Governador
1 0,01% Não eleito99 - DUPLICADO NA SECAO SEGUINTE Válido
"""


def test_extrai_candidatos_so_da_secao_resultado():
    r = analisar_texto(TEXTO)
    c = r.candidatos.set_index(["cargo", "NR_CANDIDATO"])
    assert ("Deputado Federal", "1111") not in c.index           # anexo por partido ignorado
    assert c.loc[("Governador", "99"), "votos_pdf"] == 400_000    # 1º bloco prevalece
    assert c.loc[("Governador", "99"), "situacao_pdf"] == "2º TURNO"
    assert c.loc[("Governador", "88"), "situacao_pdf"] == "NÃO ELEITO"
    assert c.loc[("Governador", "99"), "pct_pdf"] == 57.14


def test_deputados_sem_percentual_e_suplente_ordinal():
    c = analisar_texto(TEXTO).candidatos.set_index(["cargo", "NR_CANDIDATO"])
    assert c.loc[("Deputado Federal", "9999"), "situacao_pdf"] == "ELEITO POR QP"
    assert c.loc[("Deputado Federal", "8888"), "situacao_pdf"] == "SUPLENTE"
    assert c.loc[("Deputado Federal", "8888"), "votos_pdf"] == 1_234
    assert c.loc[("Deputado Federal", "7777"), "destinacao_pdf"] == "Anulado sub judice"


def test_percentual_colado_ao_numero_no_relatorio_nacional():
    c = analisar_texto(TEXTO).candidatos.set_index(["cargo", "NR_CANDIDATO"])
    assert c.loc[("Presidente", "12"), "pct_pdf"] == 60.0


def test_resumo():
    r = analisar_texto(TEXTO)
    assert r.aptos == [1_000_000] and r.abstencoes == [200_000] and r.validos == [700_000, 650_000]
