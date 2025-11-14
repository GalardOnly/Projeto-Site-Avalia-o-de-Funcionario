import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def processar_folha_ponto(arquivo_carregado):
    try:
        # Lê o arquivo
        df = pd.read_csv(arquivo_carregado, sep='\t', encoding='utf-8')
        
        # Processamento Inicial
        df['Tempo'] = pd.to_datetime(df['Tempo'], errors='coerce')
        df = df.dropna(subset=['Tempo'])
        df['Data_Apenas'] = df['Tempo'].dt.date
        df = df.sort_values(by=['Tra. No.', 'Data_Apenas', 'Tempo'])
        
        # Identifica as batidas
        df['Batida_Num'] = df.groupby(['Tra. No.', 'Data_Apenas']).cumcount()
        df['Hora'] = df['Tempo'].dt.time
        
        # Mapeia as batidas
        mapa_batidas = {0: 'Entrada', 1: 'Saida_Almoco', 2: 'Volta_Almoco', 3: 'Saida_Casa'}
        df['Tipo_Batida'] = df['Batida_Num'].map(mapa_batidas)
        
        # Cria pivot table
        df_ponto = df.pivot_table(
            index=['Tra. No.', 'Nome', 'Data_Apenas'],
            columns='Tipo_Batida', 
            values='Hora', 
            aggfunc='first'
        ).reset_index()
        
        df_ponto.columns.name = None
        
        # Garante que todas as colunas esperadas existam
        colunas_esperadas = ['Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa']
        for coluna in colunas_esperadas:
            if coluna not in df_ponto.columns:
                df_ponto[coluna] = pd.NaT
        
        # Processa datas e horas
        df_ponto['Data_Apenas'] = pd.to_datetime(df_ponto['Data_Apenas'])
        df_ponto['Dia_Semana'] = df_ponto['Data_Apenas'].dt.dayofweek
        df_ponto['Nome_Dia'] = df_ponto['Data_Apenas'].dt.day_name()
        df_ponto['Tipo_Dia'] = df_ponto['Dia_Semana'].apply(lambda x: 'Fim de Semana' if x >= 5 else 'Dia Útil')
        
        # Inicializa colunas de timedelta
        zero_delta = pd.Timedelta(0)
        
        # Converte horas para datetime - maneira mais robusta
        for coluna in colunas_esperadas:
            # Combina data com hora de forma segura
            mask = df_ponto[coluna].notna()
            df_ponto.loc[mask, f'{coluna}_dt'] = pd.to_datetime(
                df_ponto.loc[mask, 'Data_Apenas'].astype(str) + ' ' + df_ponto.loc[mask, coluna].astype(str)
            )
        
        # Horários esperados (apenas para dias úteis)
        df_ponto['Esperado_Entrada'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=7, minutes=30)
        df_ponto['Esperado_Saida_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=11, minutes=30)
        df_ponto['Esperado_Volta_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=13, minutes=0)
        df_ponto['Esperado_Saida_Casa'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=17, minutes=50)
        almoco_esperado = pd.Timedelta(minutes=89)
        
        # Inicializa todas as colunas de cálculo com timedelta zero
        colunas_calculo = [
            'Atraso_Entrada', 'Saida_Ant_Almoco', 'Atraso_Volta_Almoco', 
            'Saida_Ant_Casa', 'Almoco_Excedido', 'Horas_Extras', 'Total_Faltante'
        ]
        
        for coluna in colunas_calculo:
            df_ponto[coluna] = zero_delta
        
        # Cálculos para dias úteis (segunda a sexta)
        mask_util = df_ponto['Dia_Semana'] < 5
        
        # Função auxiliar para calcular diferença positiva
        def calcular_diferenca_positiva(actual, esperado):
            diff = (actual - esperado).fillna(zero_delta)
            # Garante que seja Timedelta antes de comparar
            diff = pd.to_timedelta(diff)
            return diff.where(diff > zero_delta, zero_delta)
        
        # Dias úteis
        if mask_util.any():
            # Atraso na entrada
            df_ponto.loc[mask_util, 'Atraso_Entrada'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Entrada_dt'],
                df_ponto.loc[mask_util, 'Esperado_Entrada']
            )
            
            # Saída antecipada almoço
            df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Esperado_Saida_Almoco'],
                df_ponto.loc[mask_util, 'Saida_Almoco_dt']
            )
            
            # Atraso volta almoço
            df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Volta_Almoco_dt'],
                df_ponto.loc[mask_util, 'Esperado_Volta_Almoco']
            )
            
            # Saída antecipada
            df_ponto.loc[mask_util, 'Saida_Ant_Casa'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Esperado_Saida_Casa'],
                df_ponto.loc[mask_util, 'Saida_Casa_dt']
            )
            
            # Almoço excedido
            almoco_real = (df_ponto.loc[mask_util, 'Volta_Almoco_dt'] - df_ponto.loc[mask_util, 'Saida_Almoco_dt']).fillna(zero_delta)
            almoco_excedido = (almoco_real - almoco_esperado).fillna(zero_delta)
            almoco_excedido = pd.to_timedelta(almoco_excedido)
            df_ponto.loc[mask_util, 'Almoco_Excedido'] = almoco_excedido.where(almoco_excedido > zero_delta, zero_delta)
            
            # Horas extras (após o horário esperado de saída)
            df_ponto.loc[mask_util, 'Horas_Extras'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Saida_Casa_dt'],
                df_ponto.loc[mask_util, 'Esperado_Saida_Casa']
            )
            
            # Total faltante (soma de todas as penalidades)
            df_ponto.loc[mask_util, 'Total_Faltante'] = (
                df_ponto.loc[mask_util, 'Atraso_Entrada'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] + 
                df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Casa'] + 
                df_ponto.loc[mask_util, 'Almoco_Excedido']
            )
        
        # Fins de semana (sábado e domingo) - CÁLCULO CORRIGIDO
        mask_fds = df_ponto['Dia_Semana'] >= 5
        if mask_fds.any():
            # Para fins de semana, calcula horas trabalhadas totais como horas extras
            # Considera TODOS os cenários possíveis de batidas
            
            # Cenário 1: Tem entrada e saída (jornada completa sem almoço ou com almoço)
            tem_entrada_saida = (
                df_ponto.loc[mask_fds, 'Entrada_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].notna()
            )
            
            # Cenário 2: Tem entrada e saída almoço (trabalhou apenas meio período)
            tem_entrada_saida_almoco = (
                df_ponto.loc[mask_fds, 'Entrada_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Almoco_dt'].notna() &
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].isna()
            )
            
            # Cenário 3: Tem volta almoço e saída (entrou antes do registro ou esqueceu de bater entrada)
            tem_volta_saida = (
                df_ponto.loc[mask_fds, 'Volta_Almoco_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].notna() &
                df_ponto.loc[mask_fds, 'Entrada_dt'].isna()
            )
            
            # Cenário 4: Tem entrada, saída almoço e volta almoço (trabalhou manhã e parte da tarde)
            tem_entrada_almoco_volta = (
                df_ponto.loc[mask_fds, 'Entrada_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Almoco_dt'].notna() &
                df_ponto.loc[mask_fds, 'Volta_Almoco_dt'].notna() &
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].isna()
            )
            
            # Calcula horas extras para cada cenário
            
            # Cenário 1: Entrada → Saída (jornada completa)
            if tem_entrada_saida.any():
                jornada_completa = (df_ponto.loc[mask_fds & tem_entrada_saida, 'Saida_Casa_dt'] - 
                                  df_ponto.loc[mask_fds & tem_entrada_saida, 'Entrada_dt']).fillna(zero_delta)
                df_ponto.loc[mask_fds & tem_entrada_saida, 'Horas_Extras'] = jornada_completa
            
            # Cenário 2: Entrada → Saída Almoço (meio período manhã)
            if tem_entrada_saida_almoco.any():
                meio_periodo_manha = (df_ponto.loc[mask_fds & tem_entrada_saida_almoco, 'Saida_Almoco_dt'] - 
                                    df_ponto.loc[mask_fds & tem_entrada_saida_almoco, 'Entrada_dt']).fillna(zero_delta)
                df_ponto.loc[mask_fds & tem_entrada_saida_almoco, 'Horas_Extras'] = meio_periodo_manha
            
            # Cenário 3: Volta Almoço → Saída (meio período tarde)
            if tem_volta_saida.any():
                meio_periodo_tarde = (df_ponto.loc[mask_fds & tem_volta_saida, 'Saida_Casa_dt'] - 
                                    df_ponto.loc[mask_fds & tem_volta_saida, 'Volta_Almoco_dt']).fillna(zero_delta)
                df_ponto.loc[mask_fds & tem_volta_saida, 'Horas_Extras'] = meio_periodo_tarde
            
            # Cenário 4: Entrada → Saída Almoço + Volta Almoço (sem saída final)
            if tem_entrada_almoco_volta.any():
                periodo_manha = (df_ponto.loc[mask_fds & tem_entrada_almoco_volta, 'Saida_Almoco_dt'] - 
                               df_ponto.loc[mask_fds & tem_entrada_almoco_volta, 'Entrada_dt']).fillna(zero_delta)
                # Se não tem saída final, considera apenas o período da manhã
                df_ponto.loc[mask_fds & tem_entrada_almoco_volta, 'Horas_Extras'] = periodo_manha
            
            # Para fins de semana, não há faltantes (todas as colunas de penalidade já estão zeradas)
        
        # Arredonda os resultados
        for col in colunas_calculo:
            df_ponto[col] = pd.to_timedelta(df_ponto[col]).round('s')
        
        # Calcula totais por funcionário
        total_mes = df_ponto.groupby('Nome')[['Total_Faltante', 'Horas_Extras']].sum()
        nomes_disponiveis = df_ponto['Nome'].unique()
        
        return df_ponto, total_mes, nomes_disponiveis
        
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        raise

# Interface Streamlit
st.set_page_config(layout="wide", page_title="Calculadora de Ponto", page_icon="⏰")

st.title("🤖 Controle de Horário de Trabalho Automático")
st.write("Faça o upload do arquivo TXT (Registo de comparec.) para processar os dados.")

with st.expander("ℹ️ **REGRAS DE CÁLCULO - CLIQUE PARA VER**"):
    st.markdown("""
    ### 📋 Regras Aplicadas:
    
    **DIAS ÚTEIS (Segunda a Sexta):**
    - ⏰ Horário esperado: 07:30 às 17:50
    - 🍽️ Almoço: 11:30 às 13:00 (máximo 89 minutos)
    - ⚠️ Penalidades calculadas:
      - Atraso na entrada (após 07:30)
      - Saída antecipada para almoço (antes das 11:30)
      - Atraso na volta do almoço (após 13:00)
      - Saída antecipada (antes das 17:50)
      - Almoço excedido (mais de 89 minutos)
    - ➕ Horas extras: Trabalho após 17:50
    
    **FINS DE SEMANA (Sábado e Domingo):**
    - ✅ Todo trabalho é considerado como horas extras
    - ❌ Não há penalidades (atrasos, etc.)
    - ⏱️ Horas extras = Tempo total trabalhado
    """)

arquivo_carregado = st.file_uploader("Escolha seu arquivo TXT", type=["txt"])

if arquivo_carregado is not None:
    try:
        with st.spinner('Processando seu arquivo...'):
            df_ponto, total_mes, nomes_disponiveis = processar_folha_ponto(arquivo_carregado)

        st.success('Arquivo processado com sucesso!')

        nome_escolhido = st.selectbox(
            "Selecione o funcionário para ver os detalhes:",
            options=nomes_disponiveis
        )

        if nome_escolhido:
            # Filtra dados do funcionário
            detalhe_diario = df_ponto[df_ponto['Nome'] == nome_escolhido].copy()
            
            # Calcula ausências
            datas_presente = pd.to_datetime(detalhe_diario['Data_Apenas']).dt.date.unique()
            dias_ausente = []
            
            if len(datas_presente) > 0:
                primeiro_dia = pd.to_datetime(min(datas_presente))
                ultimo_dia = pd.to_datetime(max(datas_presente))
                todos_dias = pd.date_range(start=primeiro_dia, end=ultimo_dia, freq='D')
                dias_uteis_esperados = [dia for dia in todos_dias if dia.dayofweek < 5]
                set_presente = set(datas_presente)
                dias_ausente = [dia for dia in dias_uteis_esperados if dia.date() not in set_presente]

            # Dashboard
            resumo_funcionario = total_mes.loc[nome_escolhido]
            st.subheader(f"Dashboard de Resumo: {nome_escolhido.upper()}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                faltante_str = str(resumo_funcionario['Total_Faltante']).split()[-1]
                st.metric(label="Total Horas Faltantes 🔻", value=faltante_str)
            with col2:
                extras_str = str(resumo_funcionario['Horas_Extras']).split()[-1]
                st.metric(label="Total Horas Extras 🔺", value=extras_str)
            with col3:
                st.metric(label="Dias com Ausência (Faltas) 🚫", value=len(dias_ausente))
            with col4:
                total_dias = len(detalhe_diario)
                st.metric(label="Total Dias Trabalhados 📅", value=total_dias)
            
            # Estatísticas por tipo de dia
            dias_uteis = detalhe_diario[detalhe_diario['Tipo_Dia'] == 'Dia Útil']
            dias_fds = detalhe_diario[detalhe_diario['Tipo_Dia'] == 'Fim de Semana']
            
            col5, col6 = st.columns(2)
            with col5:
                st.metric(label="Dias Úteis Trabalhados", value=len(dias_uteis))
            with col6:
                st.metric(label="Fins de Semana Trabalhados", value=len(dias_fds))
            
            st.write("---")

            # Lista de Ausências
            st.subheader("🚫 Ausências (Faltas em Dias Úteis)")
            if not dias_ausente:
                st.info("Nenhuma falta (ausência em dia útil) registrada no período.")
            else:
                for dia_falta in dias_ausente:
                    st.warning(f"- {dia_falta.strftime('%Y-%m-%d (%A)')}")

            # Detalhe Diário
            st.subheader(f"🗓️ Detalhe Diário: {nome_escolhido.upper()}")
            
            # Prepara dados para exibição
            colunas_exibir = [
                'Data_Apenas', 'Nome_Dia', 'Tipo_Dia', 'Entrada', 'Saida_Almoco', 
                'Volta_Almoco', 'Saida_Casa', 'Total_Faltante', 'Horas_Extras', 
                'Atraso_Entrada', 'Saida_Ant_Almoco', 'Atraso_Volta_Almoco', 
                'Saida_Ant_Casa', 'Almoco_Excedido'
            ]
            
            detalhe_exibicao = detalhe_diario[colunas_exibir].copy()
            detalhe_exibicao['Data_Apenas'] = detalhe_exibicao['Data_Apenas'].dt.strftime('%Y-%m-%d')
            
            # Formata colunas de tempo
            for col in ['Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa']:
                detalhe_exibicao[col] = detalhe_exibicao[col].apply(
                    lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '-'
                )
            
            # Formata colunas timedelta
            for col in ['Total_Faltante', 'Horas_Extras', 'Atraso_Entrada', 'Saida_Ant_Almoco',
                       'Atraso_Volta_Almoco', 'Saida_Ant_Casa', 'Almoco_Excedido']:
                detalhe_exibicao[col] = detalhe_exibicao[col].apply(
                    lambda x: str(x).split()[-1] if pd.notna(x) and str(x) != '0 days 00:00:00' else '00:00:00'
                )
            
            # Renomeia colunas
            detalhe_exibicao.columns = [
                'Data', 'Dia', 'Tipo', 'Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída',
                'Total Faltante', 'Total Extra', 'Atraso Entrada', 'Saída Ant. Almoço',
                'Atraso Volta', 'Saída Ant.', 'Almoço Excedido'
            ]
            
            st.dataframe(detalhe_exibicao, use_container_width=True)

            # Botões de Download
            st.subheader("Baixar Relatórios")
            
            # Prepara CSV para download
            df_download = df_ponto.copy()
            for col in ['Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa']:
                df_download[col] = df_download[col].apply(
                    lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else ''
                )
            
            for col in ['Total_Faltante', 'Horas_Extras', 'Atraso_Entrada', 'Saida_Ant_Almoco',
                       'Atraso_Volta_Almoco', 'Saida_Ant_Casa', 'Almoco_Excedido']:
                df_download[col] = df_download[col].apply(
                    lambda x: str(x) if pd.notna(x) else ''
                )
            
            csv_completo = df_download.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="Baixar Relatório Geral (CSV)",
                data=csv_completo,
                file_name="relatorio_completo_ponto.csv",
                mime='text/csv',
            )
            
            csv_detalhe = detalhe_exibicao.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label=f"Baixar Detalhe - {nome_escolhido} (CSV)",
                data=csv_detalhe,
                file_name=f"detalhe_{nome_escolhido}.csv",
                mime='text/csv',
            )

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
        import traceback
        st.error(f"Detalhes do erro: {traceback.format_exc()}")
