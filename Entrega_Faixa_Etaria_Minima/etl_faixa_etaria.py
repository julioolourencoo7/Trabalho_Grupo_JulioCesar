import re
import requests
import pandas as pd
import numpy as np


URL = (
    "https://apisidra.ibge.gov.br/values/t/9514/n3/all/v/93/p/2022/"
    "c2/0/c287/all/c286/113635"
)

REGIOES = {
    "Rondônia": "Norte", "Acre": "Norte", "Amazonas": "Norte",
    "Roraima": "Norte", "Pará": "Norte", "Amapá": "Norte", "Tocantins": "Norte",
    "Maranhão": "Nordeste", "Piauí": "Nordeste", "Ceará": "Nordeste",
    "Rio Grande do Norte": "Nordeste", "Paraíba": "Nordeste",
    "Pernambuco": "Nordeste", "Alagoas": "Nordeste", "Sergipe": "Nordeste",
    "Bahia": "Nordeste",
    "Minas Gerais": "Sudeste", "Espírito Santo": "Sudeste",
    "Rio de Janeiro": "Sudeste", "São Paulo": "Sudeste",
    "Paraná": "Sul", "Santa Catarina": "Sul", "Rio Grande do Sul": "Sul",
    "Mato Grosso do Sul": "Centro-Oeste", "Mato Grosso": "Centro-Oeste",
    "Goiás": "Centro-Oeste", "Distrito Federal": "Centro-Oeste",
}

def classificar_idade(rotulo):
    """Retorna 'jovens', 'adultos' ou 'idosos' para idades simples, sem somar faixas agrupadas."""
    s = str(rotulo).strip().lower()
    if "menos de 1 ano" in s:
        idade = 0
    elif "100 anos ou mais" in s:
        idade = 100
    else:
  
        m = re.fullmatch(r"(\d+)\s+anos?", s)
        if not m:
            return None
        idade = int(m.group(1))

    if idade <= 14:
        return "jovens"
    if idade <= 59:
        return "adultos"
    return "idosos"

def obter_dados():
    resposta = requests.get(URL, timeout=90)
    resposta.raise_for_status()
    registros = resposta.json()

    if not isinstance(registros, list) or len(registros) < 2:
        raise ValueError("A API do SIDRA não retornou dados no formato esperado.")

    linhas = []
    for item in registros[1:]: 
        local = item.get("D1N", "")
        idade = item.get("D5N", "")
        grupo = classificar_idade(idade)
        valor = item.get("V", "")
        if not grupo or not local:
            continue
        try:
            quantidade = int(str(valor).replace(".", "").replace(",", "."))
        except (TypeError, ValueError):
            continue
        linhas.append({"UF": local, "Faixa": grupo, "Populacao": quantidade})

    if not linhas:
        raise ValueError(
            "Não foi possível interpretar as idades retornadas pelo SIDRA. "
            "Confira a tabela 9514 e os filtros da consulta."
        )

    bruto = pd.DataFrame(linhas)
    agregado = bruto.groupby(["UF", "Faixa"], as_index=False)["Populacao"].sum()
    largo = agregado.pivot(index="UF", columns="Faixa", values="Populacao").fillna(0)

    for coluna in ["jovens", "adultos", "idosos"]:
        if coluna not in largo.columns:
            largo[coluna] = 0

    df = largo.reset_index()
    df["Regiao"] = df["UF"].map(REGIOES)
    if df["Regiao"].isna().any():
        faltantes = df.loc[df["Regiao"].isna(), "UF"].tolist()
        raise ValueError(f"Região não mapeada para: {faltantes}")

    df["Populacao_Total"] = df[["jovens", "adultos", "idosos"]].sum(axis=1)
    for grupo in ["jovens", "adultos", "idosos"]:
        df[f"Percentual_{grupo.capitalize()}"] = (
            df[grupo] / df["Populacao_Total"] * 100
        ).round(4)

    df = df.rename(columns={
        "jovens": "Populacao_Jovens_0_14",
        "adultos": "Populacao_Adultos_15_59",
        "idosos": "Populacao_Idosos_60_mais",
    })
    ordem = [
        "UF", "Regiao", "Populacao_Total",
        "Populacao_Jovens_0_14", "Percentual_Jovens",
        "Populacao_Adultos_15_59", "Percentual_Adultos",
        "Populacao_Idosos_60_mais", "Percentual_Idosos",
    ]
    df = df[ordem].sort_values(["Regiao", "UF"]).reset_index(drop=True)

    if len(df) != 27:
        raise ValueError(
            f"Esperava 27 unidades da federação, mas recebi {len(df)}. "
            "Verifique a extração antes de utilizar os resultados."
        )

    df.to_csv("dados_faixa_etaria_ibge_2022.csv", index=False, encoding="utf-8-sig")
    return df

def gerar_estatisticas(df):
    linhas = []
    for grupo in ["Jovens", "Adultos", "Idosos"]:
        coluna = f"Percentual_{grupo}"
        serie = df[coluna].dropna()
        q1 = serie.quantile(0.25)
        mediana = serie.median()
        q3 = serie.quantile(0.75)
        iqr = q3 - q1
        limite_inf = q1 - 1.5 * iqr
        limite_sup = q3 + 1.5 * iqr
        moda = serie.mode()
        outliers = df.loc[
            (df[coluna] < limite_inf) | (df[coluna] > limite_sup), ["UF", coluna]
        ]
        linhas.append({
            "Faixa_Etaria": grupo,
            "Media_%": serie.mean(),
            "Mediana_%": mediana,
            "Moda_%": moda.iloc[0] if not moda.empty else np.nan,
            "Q1_%": q1,
            "Q2_%": mediana,
            "Q3_%": q3,
            "IQR_%": iqr,
            "Amplitude_%": serie.max() - serie.min(),
            "Desvio_Padrao_%": serie.std(ddof=1),
            "Minimo_%": serie.min(),
            "Maximo_%": serie.max(),
            "Limite_Inferior_Outlier_%": limite_inf,
            "Limite_Superior_Outlier_%": limite_sup,
            "Estados_Outliers": ", ".join(outliers["UF"].tolist()) or "Nenhum",
        })
    stats = pd.DataFrame(linhas)
    stats.to_csv("estatisticas_faixa_etaria.csv", index=False, encoding="utf-8-sig")
    return stats

if __name__ == "__main__":
    dados = obter_dados()
    estatisticas = gerar_estatisticas(dados)
    print("\nBase tratada salva em: dados_faixa_etaria_ibge_2022.csv")
    print("\nEstatísticas descritivas (% da população de cada UF):")
    print(estatisticas.round(2).to_string(index=False))
    print("\nTotal nacional:")
    print(dados[["Populacao_Total", "Populacao_Jovens_0_14",
                 "Populacao_Adultos_15_59", "Populacao_Idosos_60_mais"]].sum())
