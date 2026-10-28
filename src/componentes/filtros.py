"""Barra lateral de filtros globais (Streamlit).

Mudanças vindas do mapa (clique numa UF, por exemplo) não alteram widgets
diretamente — o Streamlit proíbe alterar a chave de um widget já desenhado.
Elas são gravadas em `_acao` e aplicadas no início do próximo rerun, por
`aplicar_acao_pendente()`, antes de qualquer widget existir.
"""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from src.componentes import dados_app as dados
from src.componentes.estado import NIVEIS, NIVEL_REGIAO, NIVEL_UF, ROTULO_NIVEL, Opcoes, Selecao, sanear
from src.modelagem import vocabulario as voc

TODAS = "Todas"
SG_EXTERIOR = "ZZ"
# Cargos habilitados na interface (todos os da eleição geral).
CARGOS_HABILITADOS = {"Presidente", "Governador", "Senador", "Deputado Federal", "Deputado Estadual",
                      "Deputado Distrital"}
PADROES = {"f_turno": 1, "f_nivel": NIVEL_UF, "f_regiao": TODAS, "f_uf": None,
           "f_partidos": [], "f_paleta": "padrao", "f_fundo": "claro"}


@dataclass
class Contexto:
    sel: Selecao
    cd_cargo: int
    sg_ue: str | None           # circunscrição da disputa: 'BR', a UF, ou None (cargo estadual sem UF)
    paleta: str
    fundo: str
    rotulo_municipio: dict[str, str]
    estadual: bool = False      # cargo de circunscrição estadual (governador, senado, deputados)
    vagas: int | None = None    # vagas oficiais na circunscrição (quando houver UF/BR)
    conflito: str | None = None  # estado da disputa na UF escolhida, se não 'disponivel'
    ufs_disputa: tuple[str, ...] = ()  # UFs com a disputa disponível no cargo/turno


def agendar(**valores) -> None:
    """Agenda alterações de filtros (aplicadas no próximo rerun) e reroda o app."""
    st.session_state["_acao"] = {**st.session_state.get("_acao", {}), **valores}
    st.rerun()


def aplicar_acao_pendente() -> None:
    for k, v in st.session_state.pop("_acao", {}).items():
        st.session_state[k] = v
    for k, v in PADROES.items():
        st.session_state.setdefault(k, v)


def limpar_filtros() -> None:
    for k in list(st.session_state):
        if k.startswith(("f_", "mapa_", "cmp_", "modo_")):
            del st.session_state[k]


def barra_lateral() -> Contexto:
    aplicar_acao_pendente()
    sb = st.sidebar
    cg = dados.cargos()
    disp = dados.disponibilidade()
    # Só cargos com alguma disputa disponível nos dados, na ordem oficial do TSE.
    cargos = [c for c in cg.sort_values("CD_CARGO").DS_CARGO
              if c in CARGOS_HABILITADOS and ((disp.DS_CARGO == c) & (disp.ESTADO == voc.DISPONIVEL)).any()]
    c = sb.columns([1.3, 2])  # largura mínima para o ano não ser cortado
    c[0].selectbox("Ano", [2026], key="f_ano", help="Inicialmente apenas 2026.")
    cargo = c[1].selectbox("Cargo", cargos, key="f_cargo")
    linha_cargo = cg[cg.DS_CARGO == cargo].iloc[0]
    cd_cargo = int(linha_cargo.CD_CARGO)
    estadual = linha_cargo.TP_ABRANGENCIA != "F"

    disp_c = disp[(disp.DS_CARGO == cargo) & (disp.ESTADO == voc.DISPONIVEL)]
    turnos = sorted(disp_c.NR_TURNO.astype(int).unique())
    if st.session_state.f_turno not in turnos:
        st.session_state.f_turno = turnos[0]  # cargo sem o turno escolhido (ex.: Senado): só 1º turno existe
    turno = sb.radio("Turno", turnos, key="f_turno", format_func=lambda t: f"{t}º turno", horizontal=True)

    niveis = [n for n in NIVEIS if not (estadual and n == NIVEL_REGIAO)]
    if st.session_state.f_nivel not in niveis:
        st.session_state.f_nivel = NIVEL_UF  # regiões não agregam disputas estaduais distintas
    nivel = sb.radio("Nível geográfico", niveis, key="f_nivel", format_func=ROTULO_NIVEL.get,
                     help=None if not estadual else "Cargos estaduais: cada UF é uma disputa própria; "
                                                    "por isso não há agregação por região.")

    u = dados.ufs()
    regioes = [TODAS] + sorted(u.NM_REGIAO.unique())
    regiao = sb.selectbox("Região", regioes, key="f_regiao",
                          help="Restringe a lista de UFs, os mapas por UF e por município e os totais.")
    na_regiao = set(u.SG_UF if regiao == TODAS else u.loc[u.NM_REGIAO == regiao, "SG_UF"])
    # UFs com ESTA disputa (cargo + turno) nos dados — ex.: 2º turno de governador só onde houve.
    ufs_disputa = tuple(sorted(set(disp_c.loc[disp_c.NR_TURNO == turno, "SG_UE"]) & na_regiao)) if estadual \
        else tuple(sorted(na_regiao))
    if not estadual and regiao == TODAS and dados.tem_exterior(cd_cargo, turno):
        ufs_disputa += (SG_EXTERIOR,)  # votos no exterior: escolha própria no filtro (sem mapa)
    atual = st.session_state.f_uf
    conflito = None
    if atual is not None and atual not in ufs_disputa:
        if estadual and atual in na_regiao:
            # Não troca a UF nem o turno em silêncio: mantém a escolha e a página oferece ações.
            from src.modelagem.disponibilidade import estado
            conflito = estado(disp, cargo, atual, turno)
        else:
            st.session_state.f_uf = None
    opcoes_uf = ufs_disputa + ((atual,) if conflito else ())
    nomes_uf = dict(zip(u.SG_UF, u.NM_UF)) | {SG_EXTERIOR: "Exterior (votos fora do Brasil)"}
    uf = sb.selectbox(
        "UF" + (" (obrigatória para analisar candidatos)" if estadual else ""), [None, *opcoes_uf], key="f_uf",
        placeholder="— selecione —",
        format_func=lambda s: "— selecione —" if s is None else
        f"{s} · {nomes_uf[s]}" + (f" ({voc.ROTULOS_ESTADO[conflito].lower()})" if s == atual and conflito else ""))

    municipio, rot_mun = None, {}
    if uf and uf != SG_EXTERIOR:
        mun = dados.municipios(uf)
        rot_mun = dict(zip(mun.CD_MUNICIPIO_IBGE, mun.NOME))
        # Chave por UF: trocar a UF descarta o município da UF anterior.
        municipio = sb.selectbox("Município (digite para buscar)", [None, *mun.CD_MUNICIPIO_IBGE],
                                 key=f"f_municipio_{uf}", placeholder="— nenhum —",
                                 format_func=lambda c: "— nenhum —" if c is None else rot_mun[c])

    sg_ue = ("BR" if not estadual else (uf if uf and not conflito else None))
    if sg_ue:
        cands = dados.candidatos(cd_cargo, sg_ue, turno)
        partidos = sorted(cands.SG_PARTIDO.unique())
        circ = dados.circunscricoes()
        v = circ.loc[(circ.CD_CARGO == cd_cargo) & (circ.SG_UE == sg_ue), "QT_VAGA"]
        vagas = int(v.iloc[0]) if len(v) and v.notna().iloc[0] else None
    else:
        cands = None
        partidos = dados.ordem_partidos(cd_cargo)
        vagas = None
    st.session_state.f_partidos = [p for p in st.session_state.f_partidos if p in partidos]
    sel_partidos = sb.multiselect("Partido", partidos, key="f_partidos", placeholder="Todos",
                                  help="Afeta apenas listas e rankings. Percentuais continuam calculados "
                                       "sobre TODOS os votos válidos do cargo no território.")

    ap_box = sb.expander("Aparência")
    paleta = ap_box.radio("Paleta de liderança", ["padrao", "daltonismo"], key="f_paleta",
                      format_func={"padrao": "Padrão", "daltonismo": "Alternativa (Okabe-Ito)"}.get,
                      help="Padrão: respeita as cores de partido configuradas, mesmo que se confundam para "
                           "daltônicos. Alternativa: troca cores fixas que se confundam. No mapa escuro, "
                           "usa-se a padrão.")
    fundo = ap_box.radio("Fundo do mapa", ["claro", "escuro"], key="f_fundo", horizontal=True)
    if sb.button("Limpar filtros", use_container_width=True):
        limpar_filtros()
        st.rerun()

    sel = Selecao(cargo=cargo, turno=turno, nivel=nivel, regiao=None if regiao == TODAS else regiao,
                  uf=uf, municipio=municipio, partidos=tuple(sel_partidos))
    op = Opcoes(turnos=tuple(turnos), ufs=opcoes_uf, municipios_da_uf=frozenset(rot_mun),
                candidatos=tuple(cands.SQ_CANDIDATO) if cands is not None else (), partidos=tuple(partidos))
    sel, avisos = sanear(sel, op)
    for a in avisos:
        st.toast(a)
    return Contexto(sel, cd_cargo, sg_ue, paleta, fundo, rot_mun, estadual=estadual, vagas=vagas,
                    conflito=conflito, ufs_disputa=ufs_disputa)
