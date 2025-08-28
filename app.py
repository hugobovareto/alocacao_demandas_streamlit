import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

def main():
    st.title("📊 Sistema de Alocação de Demanda e Capacidade")
    st.markdown("""
    Esta aplicação realiza a alocação ótima de demanda não atendida para capacidade ociosa, 
    considerando:
    - Prioridade de auto-atendimento
    - Restrição de grupo (opcional)
    - Mínimo de alocação em capacidade ociosa
    """)
    
    # Upload de dados
    uploaded_file = st.file_uploader("Carregar arquivo (CSV ou Excel)", type=["csv", "xlsx", "xls"])
    
    if uploaded_file is not None:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.success(f"Dados carregados com sucesso! ({uploaded_file.name})")
    else:
        st.info("Use o formato padrão: identificador, grupo, capacidade_instalada, demanda")
        sample_data = {
            'identificador': ['CAP001', 'CAP002', 'CAP003', 'CAP004', 'CAP005', 'CAP006', 'CAP007'],
            'grupo': ['A', 'A', 'B', 'B', 'C', 'C', 'D'],
            'capacidade_instalada': [100, 150, 200, 50, 300, 120, 80],
            'demanda': [120, 100, 180, 100, 250, 150, 100]
        }
        df = pd.DataFrame(sample_data)
    
    # Mostrar dados
    st.subheader("📥 Dados de Entrada")
    st.dataframe(df)
    
    # Verificar colunas
    required_columns = {'identificador', 'grupo', 'capacidade_instalada', 'demanda'}
    if not required_columns.issubset(df.columns):
        st.error(f"Colunas necessárias não encontradas. Requeridas: {', '.join(required_columns)}")
        st.stop()
    
    # Parâmetros de configuração
    st.sidebar.header("⚙️ Configurações")
    mesmo_grupo = st.sidebar.checkbox("Alocar apenas dentro do mesmo grupo", value=True)
    min_alocacao = st.sidebar.number_input("Mínimo para alocação em capacidade ociosa", 
                                          min_value=1, value=10, step=1)
    
    if st.button("▶️ Executar Alocação"):
        with st.spinner('Otimizando alocações...'):
            resultado = calcular_alocacao(df, mesmo_grupo, min_alocacao)
        
        st.subheader("📊 Resultado Final da Alocação")
        st.dataframe(resultado['df_final'])
        
        # Botão de exportação
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            resultado['df_final'].to_excel(writer, sheet_name='Resultado', index=False)
        output.seek(0)
        
        st.download_button(
            label="📤 Exportar para Excel",
            data=output,
            file_name="resultado_alocacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.subheader("📈 Resumo da Otimização")
        resumo = resultado['resumo']
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Demanda não atendida inicial", resumo['demanda_na_inicial'])
        col2.metric("Demanda não atendida final", resumo['demanda_na_final'])
        col3.metric("Eficiência", f"{resumo['eficiencia']:.1f}%")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Capacidade ociosa inicial", resumo['capacidade_ociosa_inicial'])
        col2.metric("Capacidade ociosa final", resumo['capacidade_ociosa_final'])
        col3.metric("Demanda alocada externamente", resumo['demanda_alocada'])

def calcular_alocacao(df, mesmo_grupo, min_alocacao):
    # Cópia do DataFrame para cálculos
    df = df.copy()
    
    # Fase 1: Auto-atendimento
    df['demanda_atendida_local'] = np.minimum(df['demanda'], df['capacidade_instalada'])
    df['demanda_na'] = df['demanda'] - df['demanda_atendida_local']
    df['capacidade_ociosa'] = df['capacidade_instalada'] - df['demanda_atendida_local']
    
    # Inicializar coluna de detalhes de alocação
    df['demanda_atendida_por'] = ""
    
    # Preparar estruturas para alocação
    unidades = df.to_dict('records')
    
    # Identificar origens (demanda não atendida) e destinos (capacidade ociosa)
    origens = [u for u in unidades if u['demanda_na'] > 0]
    destinos = [u for u in unidades if u['capacidade_ociosa'] >= min_alocacao]
    
    # Ordenar para priorizar maior demanda não atendida e maior capacidade ociosa
    origens.sort(key=lambda x: x['demanda_na'], reverse=True)
    destinos.sort(key=lambda x: x['capacidade_ociosa'], reverse=True)
    
    # Dicionário para rastrear alocações
    alocacoes_detalhadas = {unidade['identificador']: [] for unidade in unidades}
    
    # Fase 2: Alocar demanda não atendida
    for origem in origens:
        if origem['demanda_na'] < min_alocacao:
            continue
            
        for destino in destinos:
            # Verificar se é a mesma unidade ou capacidade insuficiente
            if origem['identificador'] == destino['identificador'] or destino['capacidade_ociosa'] < min_alocacao:
                continue
                
            # Verificar restrição de grupo
            if mesmo_grupo and origem['grupo'] != destino['grupo']:
                continue
                
            # Calcular quantidade possível de alocar
            qtd_alocada = min(origem['demanda_na'], destino['capacidade_ociosa'])
            
            # Aplicar mínimo de alocação
            if qtd_alocada < min_alocacao:
                continue
                
            # Atualizar unidades
            origem['demanda_na'] -= qtd_alocada
            destino['capacidade_ociosa'] -= qtd_alocada
            
            # Registrar alocação detalhada
            alocacoes_detalhadas[origem['identificador']].append({
                'destino': destino['identificador'],
                'quantidade': qtd_alocada
            })
            
            # Parar se demanda totalmente alocada
            if origem['demanda_na'] < min_alocacao:
                break
    
    # Formatar detalhes de alocação
    for unidade in unidades:
        alocacoes = alocacoes_detalhadas[unidade['identificador']]
        if alocacoes:
            detalhes = []
            for aloc in alocacoes:
                detalhes.append(f"{aloc['destino']} ({aloc['quantidade']})")
            unidade['demanda_atendida_por'] = "; ".join(detalhes)
        else:
            unidade['demanda_atendida_por'] = "Auto-atendimento"
    
    # Atualizar DataFrame final
    df_final = pd.DataFrame(unidades)
    df_final['demanda_na_final'] = df_final['demanda_na']
    df_final['capacidade_ociosa_final'] = df_final['capacidade_ociosa']
    df_final['demanda_atendida_total'] = df_final['demanda'] - df_final['demanda_na_final']
    
    # Calcular métricas resumidas
    demanda_na_inicial = df['demanda_na'].sum()
    demanda_na_final = df_final['demanda_na_final'].sum()
    capacidade_ociosa_inicial = df['capacidade_ociosa'].sum()
    capacidade_ociosa_final = df_final['capacidade_ociosa_final'].sum()
    demanda_alocada = sum(len(aloc) > 0 for aloc in alocacoes_detalhadas.values())
    
    # Nova eficiência: demanda alocada / demanda não atendida inicial
    if demanda_na_inicial > 0:
        eficiencia = ((demanda_na_inicial - demanda_na_final) / demanda_na_inicial) * 100
    else:
        eficiencia = 100.0  # Se não havia demanda não atendida, eficiência é 100%
    
    resumo = {
        'demanda_na_inicial': demanda_na_inicial,
        'demanda_na_final': demanda_na_final,
        'capacidade_ociosa_inicial': capacidade_ociosa_inicial,
        'capacidade_ociosa_final': capacidade_ociosa_final,
        'demanda_alocada': demanda_na_inicial - demanda_na_final,
        'eficiencia': eficiencia
    }
    
    return {
        'df_final': df_final[['identificador', 'grupo', 'capacidade_instalada', 'demanda', 
                              'demanda_atendida_local', 'demanda_na_final', 
                              'capacidade_ociosa_final', 'demanda_atendida_por']],
        'resumo': resumo
    }

if __name__ == "__main__":
    st.set_page_config(page_title="Otimizador de Capacidade", page_icon="📊", layout="wide")
    main()