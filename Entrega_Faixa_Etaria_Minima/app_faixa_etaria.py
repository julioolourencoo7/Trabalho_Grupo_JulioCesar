import pandas as pd
import plotly.express as px
import streamlit as st
from etl_faixa_etaria import obter_dados, gerar_estatisticas

st.title('Faixa etária da população brasileira')
st.write('Censo Demográfico 2022 - IBGE')

arquivo = st.sidebar.file_uploader('Carregar base CSV ou Excel', type=['csv', 'xlsx'])
try:
    if arquivo is not None:
        if arquivo.name.endswith('.xlsx'):
            dados = pd.read_excel(arquivo)
        else:
            dados = pd.read_csv(arquivo)
    else:
        try:
            dados = pd.read_csv('dados_faixa_etaria_ibge_2022.csv')
        except FileNotFoundError:
            dados = obter_dados()
except Exception as erro:
    st.error(f'Erro ao carregar os dados: {erro}')
    st.stop()

colunas = ['UF', 'Regiao', 'Populacao_Total', 'Populacao_Jovens_0_14',
           'Populacao_Adultos_15_59', 'Populacao_Idosos_60_mais']
if not set(colunas).issubset(dados.columns):
    st.error('O arquivo precisa ter as mesmas colunas da base tratada pelo projeto.')
    st.stop()

regiao = st.sidebar.selectbox('Região', ['Todas'] + sorted(dados['Regiao'].unique().tolist()))
filtrado = dados if regiao == 'Todas' else dados[dados['Regiao'] == regiao]
uf = st.sidebar.selectbox('Estado', ['Todos'] + sorted(filtrado['UF'].unique().tolist()))
if uf != 'Todos':
    filtrado = filtrado[filtrado['UF'] == uf]

contagens = {'0 a 14 anos': 'Populacao_Jovens_0_14',
             '15 a 59 anos': 'Populacao_Adultos_15_59',
             '60 anos ou mais': 'Populacao_Idosos_60_mais'}

st.subheader('Distribuição por faixa etária')
total = filtrado['Populacao_Total'].sum()
resumo = pd.DataFrame({
    'Faixa etária': list(contagens),
    'Percentual': [100 * filtrado[c].sum() / total for c in contagens.values()]
})
st.dataframe(resumo.round(2), hide_index=True)

st.subheader('Comparação entre estados')
faixa = st.selectbox('Faixa etária', list(contagens))
comparacao = filtrado[['UF', 'Populacao_Total', contagens[faixa]]].copy()
comparacao['Percentual'] = 100 * comparacao[contagens[faixa]] / comparacao['Populacao_Total']
st.plotly_chart(px.bar(comparacao, x='UF', y='Percentual'), use_container_width=True)

st.subheader('Estatísticas descritivas')

base_stats = filtrado.copy()
for grupo, coluna in [('Jovens', 'Populacao_Jovens_0_14'),
                      ('Adultos', 'Populacao_Adultos_15_59'),
                      ('Idosos', 'Populacao_Idosos_60_mais')]:
    base_stats[f'Percentual_{grupo}'] = 100 * base_stats[coluna] / base_stats['Populacao_Total']
if len(base_stats) > 1:
    stats = gerar_estatisticas(base_stats)
    st.dataframe(stats.round(2), hide_index=True, use_container_width=True)
    box = base_stats.melt(id_vars='UF', value_vars=['Percentual_Jovens', 'Percentual_Adultos', 'Percentual_Idosos'],
                          var_name='Faixa etária', value_name='Percentual')
    st.plotly_chart(px.box(box, x='Faixa etária', y='Percentual', points='all'), use_container_width=True)
else:
    st.write('Para comparar quartis, dispersão e outliers, selecione mais de um estado.')

st.subheader('Análise descritiva')
st.write('As diferenças entre as faixas etárias ajudam a entender as necessidades de cada região. '
         'Locais com mais crianças podem precisar de maior atenção à educação; locais com mais idosos, '
         'à saúde e à acessibilidade. A composição etária não mede diretamente a densidade demográfica.')

st.subheader('Dados utilizados')
st.dataframe(filtrado, hide_index=True, use_container_width=True)
st.caption('Fonte: IBGE - Censo Demográfico 2022, SIDRA, tabela 9514.')
st.markdown('[Informações do Censo 2022 no IBGE](https://censo2022.ibge.gov.br/)')
