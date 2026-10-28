"""Filtros dependentes. DADOS SINTÉTICOS: UFs XA/XB e códigos fictícios."""
from src.componentes.estado import (NIVEL_MUNICIPIO, NIVEL_MUNICIPIO_BR, NIVEL_REGIAO, NIVEL_UF, Opcoes, Selecao,
                                    eh_municipal, filtros_ativos, nivel_consulta, sanear)

OP = Opcoes(turnos=(1, 2), ufs=("XA", "XB"), municipios_da_uf=frozenset({"9900001"}),
            candidatos=("c1", "c2", "c3"), partidos=("P1", "P2"))


def test_selecao_valida_fica_intacta():
    s = Selecao(turno=2, nivel=NIVEL_MUNICIPIO, uf="XA", municipio="9900001", candidato="c1",
                cand_a="c1", cand_b="c2", partidos=("P1",))
    assert sanear(s, OP) == (s, [])


def test_municipio_de_outra_uf_e_limpo():
    s, _ = sanear(Selecao(nivel=NIVEL_MUNICIPIO, uf="XA", municipio="1111111"), OP)
    assert s.municipio is None and s.uf == "XA"


def test_uf_invalida_limpa_uf_municipio_e_volta_ao_nivel_uf():
    s, avisos = sanear(Selecao(nivel=NIVEL_MUNICIPIO, uf="ZZ", municipio="9900001"), OP)
    assert s.uf is None and s.municipio is None and s.nivel == NIVEL_UF and avisos


def test_turno_indisponivel_nao_e_trocado_silenciosamente():
    s, avisos = sanear(Selecao(turno=2), Opcoes((1,), ("XA",), frozenset(), ("c1",), ()))
    assert s.turno == 2 and avisos  # a interface decide e oferece ações explícitas


def test_candidatos_invalidos_e_par_repetido():
    s, avisos = sanear(Selecao(candidato="c9", cand_a="c1", cand_b="c9"), OP)
    assert s.candidato is None and s.cand_a is None and s.cand_b is None and len(avisos) == 2
    s, _ = sanear(Selecao(cand_a="c1", cand_b="c1"), OP)
    assert s.cand_a is None and s.cand_b is None


def test_niveis_de_tela_para_consulta():
    assert nivel_consulta(NIVEL_REGIAO, "XA") == ("regiao", None)
    assert nivel_consulta(NIVEL_UF, "XA") == ("uf", None)
    assert nivel_consulta(NIVEL_MUNICIPIO, "XA") == ("municipio", "XA")
    assert nivel_consulta(NIVEL_MUNICIPIO_BR, "XA") == ("municipio", None)  # Brasil inteiro, mesmo com UF
    assert eh_municipal(NIVEL_MUNICIPIO_BR) and not eh_municipal(NIVEL_REGIAO)


def test_municipio_nacional_nao_exige_uf_e_aceita_municipio_da_uf():
    s, _ = sanear(Selecao(nivel=NIVEL_MUNICIPIO_BR), OP)
    assert s.nivel == NIVEL_MUNICIPIO_BR
    s, _ = sanear(Selecao(nivel=NIVEL_MUNICIPIO_BR, uf="XA", municipio="9900001"), OP)
    assert s.municipio == "9900001"


def test_filtros_ativos_mostram_regiao():
    itens = filtros_ativos(Selecao(nivel=NIVEL_UF, regiao="Sul"), {})
    assert "Região: Sul" in itens and "Brasil por UF" in itens


def test_partidos_fora_da_disputa_saem():
    s, _ = sanear(Selecao(partidos=("P1", "P9")), OP)
    assert s.partidos == ("P1",)
