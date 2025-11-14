
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
        
        # Inicializa colunas de timedelta
        zero_delta = pd.Timedelta(0)
        
        # Converte horas para datetime
        for coluna in colunas_esperadas:
            df_ponto[f'{coluna}_dt'] = pd.to_datetime(
                df_ponto['Data_Apenas'].astype(str) + ' ' + df_ponto[coluna].astype(str),
                errors='coerce'
            )
        
        # Horários esperados
        df_ponto['Esperado_Entrada'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=7, minutes=30)
        df_ponto['Esperado_Saida_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=11, minutes=30)
        df_ponto['Esperado_Volta_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=13, minutes=0)
        df_ponto['Esperado_Saida_Casa'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=17, minutes=50)
        
        # Cálculos para dias úteis (segunda a sexta)
        mask_util = df_ponto['Dia_Semana'] < 5
        
        # Inicializa todas as colunas de cálculo
        df_ponto['Atraso_Entrada'] = zero_delta
        df_ponto['Saida_Ant_Almoco'] = zero_delta
        df_ponto['Atraso_Volta_Almoco'] = zero_delta
        df_ponto['Saida_Ant_Casa'] = zero_delta
        df_ponto['Almoco_Excedido'] = zero_delta
        df_ponto['Horas_Extras'] = zero_delta
        df_ponto['Total_Faltante'] = zero_delta
        
        # Dias úteis
        if mask_util.any():
            util_df = df_ponto[mask_util]
            
            # Atraso na entrada
            atraso_entrada = (util_df['Entrada_dt'] - util_df['Esperado_Entrada']).fillna(zero_delta)
            df_ponto.loc[mask_util, 'Atraso_Entrada'] = atraso_entrada.clip(lower=zero_delta)
            
            # Saída antecipada almoço
            saida_ant_almoco = (util_df['Esperado_Saida_Almoco'] - util_df['Saida_Almoco_dt']).fillna(zero_delta)
            df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] = saida_ant_almoco.clip(lower=zero_delta)
            
            # Atraso volta almoço
            atraso_volta = (util_df['Volta_Almoco_dt'] - util_df['Esperado_Volta_Almoco']).fillna(zero_delta)
            df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] = atraso_volta.clip(lower=zero_delta)
            
            # Saída antecipada
            saida_ant_casa = (util_df['Esperado_Saida_Casa'] - util_df['Saida_Casa_dt']).fillna(zero_delta)
            df_ponto.loc[mask_util, 'Saida_Ant_Casa'] = saida_ant_casa.clip(lower=zero_delta)
            
            # Almoço excedido
            almoco_real = (util_df['Volta_Almoco_dt'] - util_df['Saida_Almoco_dt']).fillna(zero_delta)
            almoco_esperado = pd.Timedelta(minutes=89)
            almoco_excedido = (almoco_real - almoco_esperado).fillna(zero_delta)
            df_ponto.loc[mask_util, 'Almoco_Excedido'] = almoco_excedido.clip(lower=zero_delta)
            
            # Horas extras
            horas_extras = (util_df['Saida_Casa_dt'] - util_df['Esperado_Saida_Casa']).fillna(zero_delta)
            df_ponto.loc[mask_util, 'Horas_Extras'] = horas_extras.clip(lower=zero_delta)
            
            # Total faltante
            df_ponto.loc[mask_util, 'Total_Faltante'] = (
                df_ponto.loc[mask_util, 'Atraso_Entrada'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] + 
                df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Casa'] + 
                df_ponto.loc[mask_util, 'Almoco_Excedido']
            )
        
        # Fins de semana (sábado e domingo)
        mask_fds = df_ponto['Dia_Semana'] >= 5
        if mask_fds.any():
            fds_df = df_ponto[mask_fds]
            
            # Para fins de semana, calcula horas trabalhadas totais
            jornada_total = pd.Timedelta(0)
            
            # Se tem todas as 4 batidas
            completo_mask = (
                fds_df['Entrada_dt'].notna() & 
                fds_df['Saida_Almoco_dt'].notna() & 
                fds_df['Volta_Almoco_dt'].notna() & 
                fds_df['Saida_Casa_dt'].notna()
            )
            
            if completo_mask.any():
                manha = (fds_df.loc[completo_mask, 'Saida_Almoco_dt'] - fds_df.loc[completo_mask, 'Entrada_dt']).fillna(zero_delta)
                tarde = (fds_df.loc[completo_mask, 'Saida_Casa_dt'] - fds_df.loc[completo_mask, 'Volta_Almoco_dt']).fillna(zero_delta)
                jornada_total = manha + tarde
            
            # Se tem apenas entrada e saída (sem almoço)
            simples_mask = (
                fds_df['Entrada_dt'].notna() & 
                fds_df['Saida_Casa_dt'].notna() & 
                (~fds_df['Saida_Almoco_dt'].notna() | ~fds_df['Volta_Almoco_dt'].notna())
            )
            
            if simples_mask.any():
                jornada_direta = (fds_df.loc[simples_mask, 'Saida_Casa_dt'] - fds_df.loc[simples_mask, 'Entrada_dt']).fillna(zero_delta)
                df_ponto.loc[simples_mask, 'Horas_Extras'] = jornada_direta
            
            df_ponto.loc[mask_fds, 'Horas_Extras'] = jornada_total.clip(lower=zero_delta)
        
        # Arredonda os resultados
        for col in ['Atraso_Entrada', 'Saida_Ant_Almoco', 'Atraso_Volta_Almoco', 
                   'Saida_Ant_Casa', 'Almoco_Excedido', 'Horas_Extras', 'Total_Faltante']:
            df_ponto[col] = df_ponto[col].dt.round('s')
        
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
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Horas Faltantes 🔻", value=str(resumo_funcionario['Total_Faltante']))
            with col2:
                st.metric(label="Total Horas Extras 🔺", value=str(resumo_funcionario['Horas_Extras']))
            with col3:
                st.metric(label="Dias com Ausência (Faltas) 🚫", value=len(dias_ausente))
            
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
                'Data_Apenas', 'Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa',
                'Total_Faltante', 'Horas_Extras', 'Atraso_Entrada', 'Saida_Ant_Almoco',
                'Atraso_Volta_Almoco', 'Saida_Ant_Casa', 'Almoco_Excedido'
            ]
            
            detalhe_exibicao = detalhe_diario[colunas_exibir].copy()
            detalhe_exibicao['Data_Apenas'] = detalhe_exibicao['Data_Apenas'].dt.strftime('%Y-%m-%d')
            
            # Formata colunas de tempo
            for col in ['Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa']:
                detalhe_exibicao[col] = detalhe_exibicao[col].apply(
                    lambda x: x.strftime('%H:%M:%S') if pd.notna(x) else '-'
                )
            
            # Renomeia colunas
            detalhe_exibicao.columns = [
                'Data', 'Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída',
                'Total Faltante', 'Total Extra', 'Atraso Entrada', 'Saída Ant. Almoço',
                'Atraso Volta', 'Saída Ant.', 'Almoço Excedido'
            ]
            
            st.dataframe(detalhe_exibicao, use_container_width=True)

            # Botões de Download
            st.subheader("Baixar Relatórios")
            
            csv_completo = df_ponto.to_csv(index=False, encoding='utf-8')
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
        st.error("Verifique se o arquivo TXT está no formato correto.")
