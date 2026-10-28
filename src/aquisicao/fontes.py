"""Catálogo de recursos oficiais usados pelo dashboard.

As URLs foram obtidas da API CKAN do portal de dados abertos do TSE
(package_show) e da documentação da API de Malhas v3 do IBGE, na auditoria
de 28/10/2026. Nenhuma URL foi deduzida por padrão de nome sem verificação.
"""
from __future__ import annotations

from dataclasses import dataclass

CDN_TSE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
API_CKAN_TSE = "https://dadosabertos.tse.jus.br/api/3/action/package_show"
API_MALHAS_IBGE = "https://servicodados.ibge.gov.br/api/v3/malhas"


@dataclass(frozen=True)
class Recurso:
    chave: str
    fonte: str
    pacote: str | None
    descricao: str
    url: str
    arquivo: str
    essencial: bool = True


def _tse(chave: str, pacote: str, descricao: str, caminho: str, essencial: bool = True) -> Recurso:
    return Recurso(
        chave=chave,
        fonte="TSE",
        pacote=pacote,
        descricao=descricao,
        url=f"{CDN_TSE}/{caminho}",
        arquivo=caminho.split("/")[-1],
        essencial=essencial,
    )


RECURSOS_TSE: dict[str, Recurso] = {
    r.chave: r
    for r in (
        _tse("detalhe_munzona", "resultados-2026", "Detalhe da apuração por município e zona",
             "detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip"),
        _tse("votacao_candidato_munzona", "resultados-2026", "Votação nominal por município e zona",
             "votacao_candidato_munzona/votacao_candidato_munzona_2026.zip"),
        _tse("votacao_partido_munzona", "resultados-2026", "Votação em partido por município e zona",
             "votacao_partido_munzona/votacao_partido_munzona_2026.zip"),
        _tse("consulta_cand", "candidatos-2026", "Candidatos",
             "consulta_cand/consulta_cand_2026.zip"),
        _tse("consulta_vagas", "candidatos-2026", "Vagas",
             "consulta_vagas/consulta_vagas_2026.zip"),
        _tse("consulta_coligacao", "candidatos-2026", "Coligações",
             "consulta_coligacao/consulta_coligacao_2026.zip"),
        _tse("municipio_tse_ibge", "codigos-oficiais-de-uf-e-municipios-segundo-o-tse-e-o-ibge",
             "Códigos oficiais de UF e municípios segundo o TSE e o IBGE",
             "municipio_tse_ibge/municipio_tse_ibge.zip"),
    )
}


def recurso_relatorio_totalizacao(sigla: str) -> Recurso:
    """Relatório de Resultado da Totalização (PDF) de uma UF, 'BR' ou 'ZZ'.

    Usado só como referência independente na validação de totais.
    """
    sigla = sigla.upper()
    return _tse(
        f"relatorio_totalizacao_{sigla}", "resultados-2026",
        f"{sigla} - Relatório de Totalização - 2026",
        f"relatorio_resultado_totalizacao/Relatorio_Resultado_Totalizacao_2026_{sigla}.zip",
        essencial=False,
    )


# Malha Municipal 2025 (geoftp do IBGE). A API v3 entrega por padrão uma edição
# anterior sem municípios instalados depois (ex.: Boa Esperança do Norte/MT,
# IBGE 5101837), e o parâmetro `periodo` retornou HTTP 500 para 2023–2025 na
# auditoria. Por isso a fonte principal das geometrias é o FTP.
FTP_MALHA_2025 = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_municipais/municipio_2025/Brasil"
)
EDICAO_MALHA = "Malha Municipal 2025 (IBGE)"

RECURSOS_IBGE: dict[str, Recurso] = {
    "malha_municipios_2025": Recurso(
        chave="malha_municipios_2025",
        fonte="IBGE",
        pacote="Malha Municipal 2025",
        descricao="Malha municipal do Brasil, edição 2025 (shapefile, SIRGAS 2000)",
        url=f"{FTP_MALHA_2025}/BR_Municipios_2025.zip",
        arquivo="BR_Municipios_2025.zip",
    ),
}


def url_malha_ibge(nivel: str, qualidade: str, periodo: str | None = None) -> str:
    """URL da malha do Brasil subdividida por `nivel` (municipio, UF, regiao).

    `qualidade`: minima, intermediaria ou maxima (parâmetros documentados na API v3).
    """
    url = (
        f"{API_MALHAS_IBGE}/paises/BR?formato=application/vnd.geo%2Bjson"
        f"&intrarregiao={nivel}&qualidade={qualidade}"
    )
    if periodo:
        url += f"&periodo={periodo}"
    return url
