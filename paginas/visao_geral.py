"""A. Visão geral — painel: KPIs no topo, mapa central, resultado ao lado, detalhes em abas.

Cargos de circunscrição estadual (governador, senador, deputados):
- sem UF escolhida: visão nacional POR PARTIDO (cada UF é uma disputa própria);
  nunca se comparam candidatos de UFs diferentes;
- com UF: candidatos daquela disputa, nos municípios da UF.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from paginas import comum
from src.componentes import dados_app as dados
from src.componentes import mapa as cmapa
from src.componentes import visuais
from src.componentes.estado import NIVEL_MUNICIPIO, NIVEL_MUNICIPIO_BR, NIVEL_UF
from src.metricas import indicadores as m
from src.modelagem import vocabulario as voc
from src.visualizacoes import cores, graficos, mapas, modos
from src.visualizacoes import formatos as f

LIDERANCA, CANDIDATO, PARTIDO = "lideranca", "candidato", "partido"
TURNO, FINAL = "turno", "final"
ALTURA_MAPA = 480
MAX_RANKING = 25  # barras no painel lateral; a tabela completa fica nas abas


def render(ctx) -> None:
    s = ctx.sel
    esc = comum.escopo(ctx)
    visuais.cabecalho(ctx, f"{s.cargo} · {s.turno}º turno", esc.rotulo)
    if comum.bloqueio_disputa(ctx):
        return
    visuais.kpis(visuais.kpis_participacao(comum.totais_escopo(ctx, esc), esc.rotulo))
    if ctx.estadual and ctx.sg_ue is None:
        _nacional_estadual(ctx)
        return

    if st.session_state.get("f_nivel") == NIVEL_MUNICIPIO and not s.uf:
        st.info("Selecione uma UF (barra lateral) ou clique numa UF no mapa para ver os municípios.", icon="👆")

    cands = dados.candidatos(ctx.cd_cargo, ctx.sg_ue, s.turno)
    cmap, cor_outros = comum.mapa_cores(ctx)
    col_mapa, col_lado = st.columns([2.3, 1], gap="medium")
    with col_mapa, st.container(border=True):
        if esc.tipo == "exterior":
            _painel_exterior(ctx, cands, cmap, cor_outros)
        # Cargo estadual fora do nível "municípios da UF": cada UF tem disputa própria → mapa por partido.
        elif ctx.estadual and s.nivel != NIVEL_MUNICIPIO:
            _mapa_partidos(ctx, TURNO)
        else:
            _mapa(ctx, cands, cmap, cor_outros)
    with col_lado:
        r = _resultado(ctx, cands, cmap, cor_outros, esc.rotulo)

    _abas(ctx, cands, r)
    visuais.contexto_fonte(ultima_totalizacao=dados.totais(ctx.cd_cargo, s.turno, None)["ultima_totalizacao"])


# ---------------------------------------------------------------- mapas por candidato

def _mapa(ctx, cands, cmap, cor_outros) -> None:
    s = ctx.sel
    nivel_uf = not comum.mostrar_uf(ctx)   # True = hover sem sufixo de UF (região/UF)
    ap, vt = cmapa.dados_do_mapa(ctx)
    moldura = cmapa.moldura(ctx, ap, altura=ALTURA_MAPA)
    ausentes = modos.ausentes_sem_votos(ap, nivel_uf)
    rev = cmapa.revisao(ctx, "vg")
    rotulo_ausente = "Sem dado eleitoral (área sem eleitorado na malha)"
    unidade = comum.unidade(ctx)
    proporcional = comum.proporcional(ctx)

    opcoes_modo = [PARTIDO, LIDERANCA, CANDIDATO] if ctx.estadual else [LIDERANCA, CANDIDATO]
    padrao = PARTIDO if proporcional else LIDERANCA
    if st.session_state.get("modo_cor_vg") not in opcoes_modo:
        st.session_state["modo_cor_vg"] = padrao
    c = st.columns([2.1, 1.6, 1.1], vertical_alignment="bottom")
    modo = c[0].segmented_control(
        "Coloração", opcoes_modo, key="modo_cor_vg",
        format_func={PARTIDO: "Partido", LIDERANCA: "Mais votado", CANDIDATO: "Candidato"}.get) or padrao
    rot = dict(zip(cands.SQ_CANDIDATO, cands.NM_URNA_CANDIDATO + " (" + cands.SG_PARTIDO + ")"))

    if modo == PARTIDO:
        _mapa_partidos(ctx, TURNO, embutido=True)
        return
    if modo == LIDERANCA:
        intens = c[1].selectbox(
            "Intensidade", [None, modos.INTENSIDADE_PCT, modos.INTENSIDADE_VANTAGEM], key="modo_intensidade_vg",
            format_func={None: "Sem intensidade", modos.INTENSIDADE_PCT: "% do mais votado",
                         modos.INTENSIDADE_VANTAGEM: "Vantagem sobre o 2º"}.get)
        d, leg = modos.lideranca(ap, vt, cands, cmap, ctx.fundo, nivel_uf, intensidade=intens,
                                 compacto=s.nivel == NIVEL_MUNICIPIO_BR)
        fig = mapas.mapa_categorico(moldura, d, ctx.fundo, rev, ausentes, rotulo_ausente)
        presentes = set(d["COR"])
        itens = [(cmap[sq], rot[sq]) for sq in cands.SQ_CANDIDATO if cmap.get(sq) in presentes and cmap[sq] != cor_outros]
        if cor_outros in presentes:
            itens.append((cor_outros, "Não eleito (ver tooltip)" if proporcional else "Outro (ver tooltip)"))
        if leg["empates"]:
            itens.append((cores.EMPATE[ctx.fundo], f"Empate ({leg['empates']})"))
        itens.append((cores.SEM_DADO[ctx.fundo], "Sem dado"))
        visuais.legenda(itens)
        nota = f"Candidato mais votado no {unidade} — não indica eleito."
        if leg["intensidade"]:
            i = leg["intensidade"]
            nota += f" Tom claro → forte: {i['metrica']} de {f.decimal(i['min'])} a {f.decimal(i['max'])} {i['unidade']}."
        st.caption(nota)
    else:
        opcoes = cands.SQ_CANDIDATO.tolist()
        if st.session_state.get("modo_cand_vg") not in opcoes:
            st.session_state["modo_cand_vg"] = opcoes[0]
        sq = c[1].selectbox("Candidato", opcoes, key="modo_cand_vg", format_func=rot.get)
        metrica = c[2].segmented_control("Métrica", ["pct", "abs"], key="modo_metrica_vg", default="pct",
                                         format_func={"pct": "% válidos", "abs": "Votos"}.get) or "pct"
        d = modos.candidato(ap, vt, cands, sq, metrica, nivel_uf, compacto=s.nivel == NIVEL_MUNICIPIO_BR)
        zmax = float(d["Z"].max()) if d["Z"].notna().any() else 1.0
        escala = cores.escala_do_candidato(cmap.get(sq, cor_outros), ctx.fundo)
        fig = mapas.mapa_continuo(moldura, d, ctx.fundo, rev, escala, 0, zmax,
                                  "% válidos" if metrica == "pct" else "votos",
                                  hover_ausentes=ausentes, rotulo_ausente=rotulo_ausente)
        visuais.legenda([(escala[0][1], "menor"), (escala[-1][1], f"maior · {rot[sq]}"),
                         (cores.SEM_DADO[ctx.fundo], "Sem dado")])
        st.caption(("% sobre todos os votos válidos do cargo no território (não muda com filtros)."
                    + (" No Senado, cada eleitor deu dois votos: o % é de votos, não de eleitores."
                       if s.cargo == "Senador" else "")) if metrica == "pct" else
                   "⚠ Votos absolutos destacam territórios com mais eleitores; prefira % para comparar.")

    fig = mapas.destacar(fig, moldura, comum.destaque(ctx), ctx.fundo)
    cmapa.exibir(fig, ctx, "vg")
    cmapa.barra_de_acoes(ctx, "vg")


# ---------------------------------------------------------------- mapas por partido

def _nao_aplicaveis(ctx, moldura) -> dict[str, str]:
    """Territórios do mapa cuja UF não tem esta disputa no turno (ex.: sem 2º turno de governador)."""
    s = ctx.sel
    if not ctx.estadual:
        return {}
    from src.modelagem.disponibilidade import estado
    disp = dados.disponibilidade()
    u = dados.ufs()
    uf_de = dict(zip(u.CD_UF_IBGE, u.SG_UF))
    out, cache = {}, {}
    for t in moldura.ids:
        uf = t if len(t) == 2 else uf_de.get(t[:2])
        if uf is None or uf in ctx.ufs_disputa:
            continue
        if uf not in cache:
            est = estado(disp, s.cargo, uf, s.turno)
            texto = (f"Não houve segundo turno para {s.cargo.lower()}" if est == voc.NAO_HOUVE_SEGUNDO_TURNO
                     else voc.ROTULOS_ESTADO.get(est, est))
            cache[uf] = (est, texto)
        est, texto = cache[uf]
        if est != voc.DISPONIVEL:
            out[t] = f"<b>{uf}</b><br>{texto}"
    return out


def _mapa_partidos(ctx, modo_mapa: str, embutido: bool = False) -> None:
    """Mapa por partido. modo_mapa: TURNO (votos no turno) ou FINAL (eleitos oficiais por UF)."""
    s = ctx.sel
    cmap_p, cor_outros = comum.mapa_cores_partidos(ctx)
    ap, _ = cmapa.dados_do_mapa(ctx)
    moldura = cmapa.moldura(ctx, ap, altura=ALTURA_MAPA)
    rev = cmapa.revisao(ctx, "vg")
    nivel_uf = not comum.mostrar_uf(ctx)
    # "Não aplicável" só para votos de um turno; o resultado final existe em todas as UFs.
    na = _nao_aplicaveis(ctx, moldura) if modo_mapa == TURNO else {}

    if modo_mapa == FINAL:
        el = dados.eleitos(ctx.cd_cargo)
        if s.regiao:
            el = el[el.SG_UE.isin(ap.TERRITORIO)]
        if s.cargo == "Governador":
            d = modos.eleitos_por_uf(el, cmap_p, cor_outros, s.cargo)
            titulo = "Governadores eleitos — resultado final por UF"
            nota = ("Partido do eleito em cada UF (situação oficial do TSE). Algumas UFs decidiram no 1º turno, "
                    "outras no 2º — veja no tooltip.")
        else:
            circ = dados.circunscricoes()
            vagas = dict(zip(circ.loc[circ.CD_CARGO == ctx.cd_cargo, "SG_UE"],
                             circ.loc[circ.CD_CARGO == ctx.cd_cargo, "QT_VAGA"].astype(int)))
            d = modos.cadeiras_por_uf(el, vagas, cmap_p, cor_outros, cores.EMPATE[ctx.fundo])
            titulo = f"{s.cargo} — partido com mais eleitos por UF"
            nota = ("Cadeiras = eleitos pela situação oficial do TSE (nenhum cálculo de quociente). "
                    + ("Senado 2026: duas vagas por UF; “empate” = os dois eleitos são de partidos diferentes."
                       if s.cargo == "Senador" else "Empate = partidos com o mesmo número de eleitos."))
        fig = mapas.mapa_categorico(moldura, d, ctx.fundo, rev, nao_aplicaveis=na)
        presentes = set(d["COR"])
    else:
        from src.componentes.estado import nivel_consulta
        nivel, uf = nivel_consulta(s.nivel, s.uf)
        regiao = s.regiao
        pt = dados.partidos_territorios(ctx.cd_cargo, s.turno, nivel, uf, regiao)
        d, leg = modos.lideranca_partido(ap, pt, cmap_p, ctx.fundo, nivel_uf, compacto=s.nivel == NIVEL_MUNICIPIO_BR)
        fig = mapas.mapa_categorico(moldura, d, ctx.fundo, rev, modos.ausentes_sem_votos(ap, nivel_uf),
                                    nao_aplicaveis=na)
        presentes = set(d["COR"])
        titulo = f"Partido mais votado por {comum.unidade(ctx)} · {s.turno}º turno"
        nota = ("Votos do partido = nominais dos seus candidatos + legenda, ÷ válidos do cargo. "
                if comum.proporcional(ctx) else "Partido do candidato mais votado. ")
        if ctx.estadual and s.nivel != NIVEL_MUNICIPIO:
            nota += "Cada UF tem sua própria disputa: as cores mostram partidos, não candidatos comparáveis entre UFs."

    if not embutido:
        st.markdown(f"**{titulo}**")
    itens = [(cmap_p[p], p) for p in cmap_p if cmap_p[p] in presentes and cmap_p[p] != cor_outros]
    if cor_outros in presentes:
        itens.append((cor_outros, "Outros partidos (ver tooltip)"))
    if cores.EMPATE[ctx.fundo] in presentes:
        itens.append((cores.EMPATE[ctx.fundo], "Empate"))
    if na:
        itens.append((cores.NAO_APLICAVEL[ctx.fundo], "Não aplicável" if s.turno == 1 else "Não houve 2º turno"))
    itens.append((cores.SEM_DADO[ctx.fundo], "Sem dado"))
    visuais.legenda(itens)
    st.caption(nota)
    fig = mapas.destacar(fig, moldura, comum.destaque(ctx), ctx.fundo)
    cmapa.exibir(fig, ctx, "vg")
    cmapa.barra_de_acoes(ctx, "vg")


def _nacional_estadual(ctx) -> None:
    """Cargo estadual sem UF: visão nacional por partido, com escopo explícito."""
    s = ctx.sel
    st.info(f"**{s.cargo}: cada UF tem sua própria disputa.** Esta visão mostra partidos e eleitos oficiais; "
            "para comparar candidatos, escolha uma UF (barra lateral) ou clique numa UF do mapa.", icon="🗺️")
    col_mapa, col_lado = st.columns([2.3, 1], gap="medium")
    with col_mapa, st.container(border=True):
        opcoes = [TURNO, FINAL] if s.nivel == NIVEL_UF else [TURNO]
        rot_final = "Eleitos (resultado final)" if s.cargo == "Governador" else "Eleitos por partido"
        modo_mapa = st.segmented_control("Mapa", opcoes, key="modo_mapa_nac", default=TURNO,
                                         format_func={TURNO: f"Votos no {s.turno}º turno", FINAL: rot_final}.get) or TURNO
        if s.nivel == NIVEL_MUNICIPIO_BR:
            st.caption("No mapa por município, cores mostram o partido mais votado (cada município pertence "
                       "à disputa da sua UF).")
        _mapa_partidos(ctx, modo_mapa)
    with col_lado, st.container(border=True):
        _eleitos_por_partido(ctx)
    visuais.contexto_fonte(ultima_totalizacao=dados.totais(ctx.cd_cargo, s.turno, None)["ultima_totalizacao"])


def _eleitos_por_partido(ctx, sg_ue: str | None = None) -> None:
    s = ctx.sel
    el = dados.eleitos(ctx.cd_cargo, sg_ue)
    if s.regiao and not sg_ue:
        u = dados.ufs()
        el = el[el.SG_UE.isin(u.loc[u.NM_REGIAO == s.regiao, "SG_UF"])]
    st.markdown("### Eleitos por partido")
    st.caption(f"{len(el)} eleitos · situação oficial do TSE" + (f" · {s.regiao}" if s.regiao and not sg_ue else ""))
    if el.empty:
        return
    cont = el.SG_PARTIDO.value_counts().rename_axis("Partido").reset_index(name="Eleitos")
    cmap_p, cor_outros = comum.mapa_cores_partidos(ctx)
    st.plotly_chart(graficos.barras_contagem(cont, "Partido", "Eleitos", cmap_p, cor_outros, ctx.fundo),
                    use_container_width=True, config={"displayModeBar": False}, key=f"eleitos_{sg_ue}")
    if s.cargo in ("Governador", "Senador") and not sg_ue:
        with st.expander("Eleitos por UF"):
            st.dataframe(el[["SG_UE", "NM_URNA_CANDIDATO", "SG_PARTIDO", "TURNO_ELEICAO", "VOTOS"]].rename(columns={
                "SG_UE": "UF", "NM_URNA_CANDIDATO": "Eleito", "SG_PARTIDO": "Partido",
                "TURNO_ELEICAO": "Turno", "VOTOS": "Votos"}), hide_index=True, use_container_width=True,
                column_config={"Votos": st.column_config.NumberColumn(format="localized")})


# ---------------------------------------------------------------- painel lateral e abas

def _resultado(ctx, cands, cmap, cor_outros, rotulo) -> pd.DataFrame:
    s = ctx.sel
    r = comum.ranking_escopo(ctx, cands)
    if s.partidos:
        r = r[r.SG_PARTIDO.isin(s.partidos)]
    with st.container(border=True):
        st.markdown("### Resultado")
        eleitos = cands[cands.SITUACAO_FINAL.eq("eleito")]
        if len(eleitos) == 1:
            e = eleitos.iloc[0]
            visuais.selo_eleito(f"Eleito (TSE): {e.NM_URNA_CANDIDATO} ({e.SG_PARTIDO}) · {int(e.TURNO_ELEICAO)}º turno")
        elif len(eleitos) > 1:
            nomes = ", ".join(eleitos.NM_URNA_CANDIDATO.head(3))
            visuais.selo_eleito(f"{len(eleitos)} eleitos (TSE){' de ' + str(ctx.vagas) + ' vagas' if ctx.vagas else ''}"
                                + (f": {nomes}" if len(eleitos) <= 3 else " — ver aba Eleitos"))
        den = r["VALIDOS_CIRCUNSCRICAO"].dropna()
        st.caption(f"{rotulo} · % sobre {f.inteiro(den.iloc[0]) if len(den) else '—'} válidos"
                   + (" · filtro de partido não altera o denominador" if s.partidos else "")
                   + (" · Senado: dois votos por eleitor" if s.cargo == "Senador" else "")
                   + (f" · top {MAX_RANKING} de {len(r)}" if len(r) > MAX_RANKING else ""))
        with st.container(height=ALTURA_MAPA - 30, border=False):
            st.plotly_chart(graficos.ranking(r.head(MAX_RANKING), cmap, cor_outros, ctx.fundo),
                            use_container_width=True, config={"displayModeBar": False}, key="rank_vg")
    return r


def _abas(ctx, cands, r) -> None:
    s = ctx.sel
    nivel_brasil = comum.escopo(ctx).tipo == "brasil"
    nomes = ["Candidatos", "Partidos / federações"]
    if ctx.estadual:
        nomes.append("Eleitos")
    if nivel_brasil and not ctx.estadual:
        nomes.append("Exterior")
    nomes.append("Como ler")
    abas = dict(zip(nomes, st.tabs(nomes)))

    with abas["Candidatos"]:
        situacoes = sorted(r.SITUACAO_TURNO.dropna().unique())
        filtro = st.multiselect("Situação oficial", situacoes, key="vg_situacao", placeholder="Todas")
        t = r[r.SITUACAO_TURNO.isin(filtro)] if filtro else r
        st.dataframe(
            t[["NM_URNA_CANDIDATO", "NR_CANDIDATO", "SG_PARTIDO", "VOTOS", "PCT_VALIDOS", "SITUACAO_TURNO"]].rename(columns={
                "NM_URNA_CANDIDATO": "Candidato", "NR_CANDIDATO": "Número", "SG_PARTIDO": "Partido", "VOTOS": "Votos",
                "PCT_VALIDOS": "% válidos", "SITUACAO_TURNO": "Situação oficial no turno"}),
            hide_index=True, use_container_width=True, height=visuais.altura_tabela(len(t), 300),
            column_config={"Votos": st.column_config.NumberColumn(format="localized"),
                           "% válidos": st.column_config.NumberColumn(format="%.2f%%")})
        st.caption(f"{len(t)} candidatos. Votos nominais válidos no recorte.")
        visuais.botao_csv(t[["NM_URNA_CANDIDATO", "NR_CANDIDATO", "SG_PARTIDO", "VOTOS", "PCT_VALIDOS",
                             "SITUACAO_TURNO"]], f"candidatos_{s.cargo}_{s.turno}t_{comum.escopo(ctx).rotulo}")

    with abas["Partidos / federações"]:
        if ctx.estadual and ctx.sg_ue and ctx.sg_ue != "BR" and comum.escopo(ctx).tipo == "uf":
            _resumo_partidos(ctx)
        else:
            por = r.assign(GRUPO=r.NM_FEDERACAO.fillna(r.SG_PARTIDO)).groupby("GRUPO", as_index=False)[["VOTOS"]].sum()
            den = r["VALIDOS_CIRCUNSCRICAO"].dropna()
            por["PCT"] = 100 * por.VOTOS / den.iloc[0] if len(den) else float("nan")
            st.plotly_chart(graficos.barras_partido(por, "GRUPO", "PCT", ctx.fundo, cores.SEQUENCIAL_AZUL[4]),
                            use_container_width=True, config={"displayModeBar": False}, key="part_vg")
            st.caption("Votos nominais válidos dos candidatos de cada partido/federação ÷ válidos do recorte"
                       + (" (votos de legenda: veja o recorte da UF inteira)." if ctx.estadual else "."))

    if "Eleitos" in abas:
        with abas["Eleitos"]:
            el = dados.eleitos(ctx.cd_cargo, ctx.sg_ue)
            st.dataframe(el[["NM_URNA_CANDIDATO", "NR_CANDIDATO", "SG_PARTIDO", "NM_FEDERACAO", "SITUACAO", "TURNO_ELEICAO",
                             "VOTOS"]].rename(columns={
                "NM_URNA_CANDIDATO": "Eleito", "NR_CANDIDATO": "Número", "SG_PARTIDO": "Partido",
                "NM_FEDERACAO": "Federação", "SITUACAO": "Situação oficial", "TURNO_ELEICAO": "Turno",
                "VOTOS": "Votos (UF)"}), hide_index=True, use_container_width=True,
                height=visuais.altura_tabela(len(el), 300),
                column_config={"Votos (UF)": st.column_config.NumberColumn(format="localized")})
            st.caption(f"{len(el)} eleitos{f' para {ctx.vagas} vagas' if ctx.vagas else ''} — situação oficial do TSE. "
                       "Eleitos não são definidos pelo ranking de votos (há quociente partidário e sobras).")

    if "Exterior" in abas:
        with abas["Exterior"]:
            _exterior(ctx, cands)

    with abas["Como ler"]:
        st.markdown(
            "- **Mais votado no território** não é **eleito**: o resultado vale para a circunscrição "
            "(selo dourado e aba Eleitos, situação oficial do TSE).\n"
            "- **Percentuais** = votos ÷ válidos do cargo no território, somando numeradores e denominadores "
            "antes de dividir. Filtros de candidato/partido não mudam o denominador.\n"
            "- **Cargos estaduais**: cada UF é uma disputa própria; candidatos de UFs diferentes não são comparados.\n"
            "- **Senado 2026**: duas vagas por UF e dois votos por eleitor; percentuais são de votos, não de eleitores.\n"
            "- **Deputados**: votos do partido = nominais dos candidatos + legenda. Eleitos vêm da situação oficial "
            "(quociente partidário e médias), nunca do ranking de votos.\n"
            "- **Cinza sólido** = disputa inexistente no recorte (ex.: UF sem 2º turno); **branco** = sem dado.")


def _resumo_partidos(ctx) -> None:
    rp = dados.resumo_partidos(ctx.cd_cargo, ctx.sg_ue, ctx.sel.turno)
    st.dataframe(rp[["SG_PARTIDO", "NM_FEDERACAO", "NOMINAIS", "LEGENDA", "TOTAL", "PCT_VALIDOS", "ELEITOS",
                     "ELEITOS_QP", "ELEITOS_MEDIA"]].rename(columns={
        "SG_PARTIDO": "Partido", "NM_FEDERACAO": "Federação", "NOMINAIS": "Votos nominais", "LEGENDA": "Votos de legenda",
        "TOTAL": "Total", "PCT_VALIDOS": "% válidos", "ELEITOS": "Eleitos", "ELEITOS_QP": "por QP",
        "ELEITOS_MEDIA": "por média"}), hide_index=True, use_container_width=True,
        height=visuais.altura_tabela(len(rp), 320),
        column_config={c: st.column_config.NumberColumn(format="localized")
                       for c in ("Votos nominais", "Votos de legenda", "Total")}
        | {"% válidos": st.column_config.NumberColumn(format="%.2f%%")})
    fed = rp.assign(GRUPO=rp.NM_FEDERACAO.fillna(rp.SG_PARTIDO)).groupby("GRUPO", as_index=False)[
        ["NOMINAIS", "LEGENDA", "TOTAL", "ELEITOS"]].sum().sort_values(["ELEITOS", "TOTAL"], ascending=False)
    with st.expander("Resumo por federação / partido isolado"):
        st.dataframe(fed.rename(columns={"GRUPO": "Federação ou partido", "NOMINAIS": "Nominais", "LEGENDA": "Legenda",
                                         "TOTAL": "Total", "ELEITOS": "Eleitos"}), hide_index=True, use_container_width=True)
    st.caption(f"{ctx.sg_ue} · {ctx.sel.turno}º turno. Eleitos = situação oficial do TSE (QP = quociente partidário; "
               "média = distribuição das sobras). O painel não recalcula cadeiras.")


def _painel_exterior(ctx, cands, cmap, cor_outros) -> None:
    """Votos no exterior: por país (mapa-múndi + tabela) ou por cidade (tabela)."""
    loc = dados.exterior_localidades(ctx.cd_cargo, ctx.sel.turno)
    if loc.empty:
        st.caption("Sem votos no exterior neste turno.")
        return
    vista = st.segmented_control("Votos no exterior", ["pais", "cidade"], key="ext_vista", default="pais",
                                 format_func={"pais": "Por país", "cidade": "Por cidade"}.get) or "pais"
    if vista == "pais":
        _exterior_por_pais(ctx, cands, cmap, cor_outros, loc)
    else:
        _exterior_por_cidade(ctx, cands, loc)


def _exterior_por_pais(ctx, cands, cmap, cor_outros, loc) -> None:
    from src.consultas.exterior import por_pais
    ap, vt, sem_pais = por_pais(loc)
    d, leg = modos.lideranca(ap, vt, cands, cmap, ctx.fundo, nivel_uf=True)
    d["HOVER"] = [h.replace("</b>", f"</b> · {int(c)} cidade(s)", 1)
                  for h, c in zip(d["HOVER"], d["TERRITORIO"].map(dict(zip(ap.TERRITORIO, ap.CIDADES))))]
    st.plotly_chart(mapas.mapa_mundi(d, ctx.fundo), use_container_width=True, key="ext_mundi",
                    config={"scrollZoom": True, "displaylogo": False})
    rot = dict(zip(cands.SQ_CANDIDATO, cands.NM_URNA_CANDIDATO + " (" + cands.SG_PARTIDO + ")"))
    presentes = set(d["COR"])
    itens = [(cmap[sq], rot[sq]) for sq in cands.SQ_CANDIDATO if cmap.get(sq) in presentes and cmap[sq] != cor_outros]
    if cor_outros in presentes:
        itens.append((cor_outros, "Outro (ver tooltip)"))
    if leg["empates"]:
        itens.append((cores.EMPATE[ctx.fundo], "Empate"))
    itens.append(("#14213d", "Brasil (referência)"))
    visuais.legenda(itens)
    st.caption("Mais votado por país, somando as cidades do exterior de cada país. Países agrupados pela tabela "
               "auxiliar config/exterior_paises.csv (classificação geográfica revisável; o TSE publica só a cidade)."
               + (f" Cidades sem país na tabela: {', '.join(sem_pais)}." if sem_pais else ""))
    piv = vt.pivot_table(index="TERRITORIO", columns="SQ_CANDIDATO", values="VOTOS", aggfunc="sum", fill_value=0)
    tab = ap.set_index("TERRITORIO")
    tabela = pd.DataFrame({"País": tab.NOME, "Cidades": tab.CIDADES, "Aptos": tab.QT_APTOS,
                           "Comparecimento %": m.percentual(tab.QT_COMPARECIMENTO, tab.QT_APTOS)}, index=tab.index)
    for sq in [s for s in cands.SQ_CANDIDATO if s in piv.columns][:3]:
        tabela[f"% {cands.set_index('SQ_CANDIDATO').NM_URNA_CANDIDATO[sq]}"] = m.percentual(
            piv[sq].reindex(tab.index).fillna(0), tab.QT_TOTAL_VOTOS_VALIDOS)
    st.dataframe(tabela.sort_values("Aptos", ascending=False), hide_index=True, use_container_width=True,
                 height=visuais.altura_tabela(len(tabela), 320),
                 column_config={"Aptos": st.column_config.NumberColumn(format="localized")}
                 | {c: st.column_config.NumberColumn(format="%.1f%%") for c in tabela.columns if "%" in c})


def _exterior_por_cidade(ctx, cands, loc) -> None:
    rot = dict(zip(cands.SQ_CANDIDATO, cands.NM_URNA_CANDIDATO))
    st.caption("As cidades no exterior não têm geometria no mapa do Brasil. Os votos entram no total nacional "
               "de presidente. % sobre os válidos da cidade.")
    piv = loc.pivot_table(index=["CD_MUNICIPIO", "LOCALIDADE", "APTOS", "COMPARECIMENTO", "VALIDOS"],
                          columns="SQ_CANDIDATO", values="VOTOS", aggfunc="sum", fill_value=0).reset_index()
    top = [sq for sq in cands.SQ_CANDIDATO if sq in piv.columns][:3]
    tab = pd.DataFrame({"Cidade": piv.LOCALIDADE.str.title(), "Aptos": piv.APTOS,
                        "Comparecimento %": m.percentual(piv.COMPARECIMENTO, piv.APTOS)})
    cand_cols = [c for c in piv.columns if c in rot]
    lider = piv[cand_cols].idxmax(axis=1).where(piv.VALIDOS > 0)
    tab["Mais votado"] = lider.map(rot).fillna("— sem votos válidos")
    for sq in top:
        tab[f"% {rot[sq]}"] = m.percentual(piv[sq], piv.VALIDOS)
    filtro = st.text_input("Buscar cidade", key="ext_busca", placeholder="ex.: Lisboa, Boston, Tóquio")
    if filtro:
        tab = tab[tab.Cidade.str.contains(filtro, case=False, na=False)]
    st.dataframe(tab.sort_values("Aptos", ascending=False), hide_index=True, use_container_width=True, height=420,
                 column_config={"Aptos": st.column_config.NumberColumn(format="localized"),
                                "Comparecimento %": st.column_config.NumberColumn(format="%.1f%%")}
                 | {f"% {rot[sq]}": st.column_config.NumberColumn(format="%.1f%%") for sq in top})
    st.caption(f"{len(piv)} cidades · ordenadas pelo eleitorado apto.")


def _exterior(ctx, cands) -> None:
    ex = dados.exterior(ctx.cd_cargo, ctx.sel.turno)
    if ex.empty:
        st.caption("Sem votos no exterior para este cargo.")
        return
    rot = dict(zip(cands.SQ_CANDIDATO, cands.NM_URNA_CANDIDATO + " (" + cands.SG_PARTIDO + ")"))
    visuais.kpis([
        ("Localidades", str(int(ex.LOCALIDADES.iloc[0])), "sem geometria no mapa", "Cidades no exterior (UF ZZ)"),
        ("Eleitorado apto", f.compacto(ex.APTOS.iloc[0]), f.inteiro(ex.APTOS.iloc[0]), ""),
        ("Comparecimento", f.compacto(ex.COMPARECIMENTO.iloc[0]), f.inteiro(ex.COMPARECIMENTO.iloc[0]), ""),
        ("Válidos", f.compacto(ex.VALIDOS.iloc[0]), "incluídos no total do Brasil", ""),
    ])
    st.dataframe(pd.DataFrame({"Candidato": ex.SQ_CANDIDATO.map(rot), "Votos": ex.VOTOS,
                               "% válidos no exterior": ex.PCT_VALIDOS}),
                 hide_index=True, use_container_width=True, height=visuais.altura_tabela(len(ex), 300),
                 column_config={"Votos": st.column_config.NumberColumn(format="localized"),
                                "% válidos no exterior": st.column_config.NumberColumn(format="%.2f%%")})
