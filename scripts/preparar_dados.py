"""Atualização manual e explícita dos dados.

Uso (PowerShell, na raiz do projeto, com o venv ativo):
    python -m scripts.preparar_dados baixar               # recursos essenciais (TSE + malha IBGE)
    python -m scripts.preparar_dados baixar --forcar      # ignora cache local
    python -m scripts.preparar_dados baixar --so detalhe_munzona consulta_cand
    python -m scripts.preparar_dados importar consulta_cand C:\\caminho\\consulta_cand_2026.zip
    python -m scripts.preparar_dados auditar              # Parquet bruto + perfil + consistência
    python -m scripts.preparar_dados geografia            # processa malhas e junção TSE–IBGE
    python -m scripts.preparar_dados modelar              # modelo tipado, agregados, qualidade
    python -m scripts.preparar_dados validar ES BR        # confronto com relatórios oficiais (PDF)
    python -m scripts.preparar_dados listar               # catálogo e manifesto
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.aquisicao import manifesto
from src.aquisicao.download import baixar, importar_local
from src.aquisicao.fontes import RECURSOS_IBGE, RECURSOS_TSE
from src.config import garantir_diretorios

RECURSOS = {**RECURSOS_TSE, **RECURSOS_IBGE}


def cmd_baixar(args: argparse.Namespace) -> None:
    chaves = args.so or [k for k, r in RECURSOS.items() if r.essencial]
    for chave in chaves:
        baixar(RECURSOS[chave], forcar=args.forcar)


def cmd_importar(args: argparse.Namespace) -> None:
    importar_local(RECURSOS[args.chave], Path(args.arquivo))


def cmd_geografia(_: argparse.Namespace) -> None:
    from src.geografia.preparar import preparar_geografia
    preparar_geografia()


def cmd_auditar(_: argparse.Namespace) -> None:
    from src.validacao.auditoria import auditar
    from src.validacao.consistencia import relatorio
    auditar()
    falhas = [r for r in relatorio() if r[3]]
    print(f"[consistência] {len(falhas)} verificação(ões) com violação; ver docs/relatorios/consistencia.md")
    for nome, _, grupo, viol, total in falhas:
        print(f"    FALHA {nome} [{grupo}]: {viol} de {total}")


def cmd_modelar(_: argparse.Namespace) -> None:
    from src.modelagem import agregados, construir, disponibilidade
    from src.validacao import qualidade
    construir.construir()
    disponibilidade.salvar()
    agregados.construir()
    r = qualidade.relatorio()
    print(f"[qualidade] falhas de granularidade: {r['falhas_granularidade'] or 'nenhuma'}; "
          "ver docs/relatorios/qualidade_modelo.md")


def cmd_validar(args: argparse.Namespace) -> None:
    from src.validacao.referencia_totalizacao import relatorio
    for sg, r in relatorio([s.upper() for s in args.circunscricoes]).items():
        problemas = {k: v for k, v in r.items() if k not in ("candidatos_comparados", "pct_comparados") and v not in (0, True)}
        print(f"[validar] {sg}: {r['candidatos_comparados']} candidatos comparados; "
              f"{'sem divergências' if not problemas else problemas}")
    print("    ver docs/relatorios/validacao_totalizacao.md")


def cmd_listar(_: argparse.Namespace) -> None:
    m = manifesto.carregar()["recursos"]
    for chave, r in RECURSOS.items():
        reg = m.get(chave)
        estado = f"baixado em {reg['baixado_em']}" if reg else "não baixado"
        print(f"{chave:28s} {estado}\n    {r.url}")


def main() -> None:
    garantir_diretorios()
    p = argparse.ArgumentParser(description="Preparação de dados do dashboard Eleições 2026")
    sub = p.add_subparsers(dest="comando", required=True)

    b = sub.add_parser("baixar", help="Baixa recursos oficiais")
    b.add_argument("--so", nargs="+", choices=sorted(RECURSOS))
    b.add_argument("--forcar", action="store_true")
    b.set_defaults(func=cmd_baixar)

    i = sub.add_parser("importar", help="Importa arquivo oficial obtido manualmente")
    i.add_argument("chave", choices=sorted(RECURSOS))
    i.add_argument("arquivo")
    i.set_defaults(func=cmd_importar)

    sub.add_parser("geografia", help="Processa malhas e junção TSE–IBGE").set_defaults(func=cmd_geografia)
    sub.add_parser("auditar", help="Perfil dos arquivos brutos").set_defaults(func=cmd_auditar)
    sub.add_parser("modelar", help="Modelo tipado, disponibilidade, agregados e qualidade").set_defaults(func=cmd_modelar)
    v = sub.add_parser("validar", help="Compara com o Relatório de Totalização (PDF) do TSE")
    v.add_argument("circunscricoes", nargs="+", help="UFs e/ou BR (presidente nacional), ex.: ES BR")
    v.set_defaults(func=cmd_validar)
    sub.add_parser("listar", help="Mostra catálogo e manifesto").set_defaults(func=cmd_listar)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
