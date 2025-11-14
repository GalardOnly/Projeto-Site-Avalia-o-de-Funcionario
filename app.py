
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def processar_folha_ponto(arquivo_carregado):
    try:
        
        df = pd.read_csv(arquivo_carregado, sep='\t', encoding='utf-8')
        
        
        df['Tempo'] = pd.to_datetime(df['Tempo'], errors='coerce')
        df = df.dropna(subset=['Tempo'])
        df['Data_Apenas'] = df['Tempo'].dt.date
        df = df.sort_values(by=['Tra. No.', 'Data_Apenas', 'Tempo'])
        
       
        df['Batida_Num'] = df.groupby(['Tra. No.', 'Data_Apenas']).cumcount()
        df['Hora'] = df['Tempo'].dt.time
        
        
        mapa_batidas = {0: 'Entrada', 1: 'Saida_Almoco', 2: 'Volta_Almoco', 3: 'Saida_Casa'}
        df['Tipo_Batida'] = df['Batida_Num'].map(mapa_batidas)
        
      
        df_ponto = df.pivot_table(
            index=['Tra. No.', 'Nome', 'Data_Apenas'],
            columns='Tipo_Batida', 
            values='Hora', 
            aggfunc='first'
        ).reset_index()
        
        df_ponto.columns.name = None
        
        
        colunas_esperadas = ['Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa']
        for coluna in colunas_esperadas:
            if coluna not in df_ponto.columns:
                df_ponto[coluna] = pd.NaT
        
   
        df_ponto['Data_Apenas'] = pd.to_datetime(df_ponto['Data_Apenas'])
        df_ponto['Dia_Semana'] = df_ponto['Data_Apenas'].dt.dayofweek
        df_ponto['Nome_Dia'] = df_ponto['Data_Apenas'].dt.day_name()
        df_ponto['Tipo_Dia'] = df_ponto['Dia_Semana'].apply(lambda x: 'Fim de Semana' if x >= 5 else 'Dia Útil')
        
        zero_delta = pd.Timedelta(0)
        
        for coluna in colunas_esperadas:
           
            mask = df_ponto[coluna].notna()
            df_ponto.loc[mask, f'{coluna}_dt'] = pd.to_datetime(
                df_ponto.loc[mask, 'Data_Apenas'].astype(str) + ' ' + df_ponto.loc[mask, coluna].astype(str)
            )
        
        df_ponto['Esperado_Entrada'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=7, minutes=30)
        df_ponto['Esperado_Saida_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=11, minutes=30)
        df_ponto['Esperado_Volta_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=13, minutes=0)
        df_ponto['Esperado_Saida_Casa'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=17, minutes=50)
        almoco_esperado = pd.Timedelta(minutes=89)
        
        colunas_calculo = [
            'Atraso_Entrada', 'Saida_Ant_Almoco', 'Atraso_Volta_Almoco', 
            'Saida_Ant_Casa', 'Almoco_Excedido', 'Horas_Extras', 'Total_Faltante'
        ]
        
        for coluna in colunas_calculo:
            df_ponto[coluna] = zero_delta
        
        mask_util = df_ponto['Dia_Semana'] < 5
        
    
        def calcular_diferenca_positiva(actual, esperado):
            diff = (actual - esperado).fillna(zero_delta)
          
            diff = pd.to_timedelta(diff)
            return diff.where(diff > zero_delta, zero_delta)
     
        if mask_util.any():
            df_ponto.loc[mask_util, 'Atraso_Entrada'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Entrada_dt'],
                df_ponto.loc[mask_util, 'Esperado_Entrada']
            )
           
            df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Esperado_Saida_Almoco'],
                df_ponto.loc[mask_util, 'Saida_Almoco_dt']
            )
           
            df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Volta_Almoco_dt'],
                df_ponto.loc[mask_util, 'Esperado_Volta_Almoco']
            )
          
            df_ponto.loc[mask_util, 'Saida_Ant_Casa'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Esperado_Saida_Casa'],
                df_ponto.loc[mask_util, 'Saida_Casa_dt']
            )
         
            almoco_real = (df_ponto.loc[mask_util, 'Volta_Almoco_dt'] - df_ponto.loc[mask_util, 'Saida_Almoco_dt']).fillna(zero_delta)
            almoco_excedido = (almoco_real - almoco_esperado).fillna(zero_delta)
            almoco_excedido = pd.to_timedelta(almoco_excedido)
            df_ponto.loc[mask_util, 'Almoco_Excedido'] = almoco_excedido.where(almoco_excedido > zero_delta, zero_delta)
            
            df_ponto.loc[mask_util, 'Horas_Extras'] = calcular_diferenca_positiva(
                df_ponto.loc[mask_util, 'Saida_Casa_dt'],
                df_ponto.loc[mask_util, 'Esperado_Saida_Casa']
            )
            
            df_ponto.loc[mask_util, 'Total_Faltante'] = (
                df_ponto.loc[mask_util, 'Atraso_Entrada'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] + 
                df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Casa'] + 
                df_ponto.loc[mask_util, 'Almoco_Excedido']
            )
        
        mask_fds = df_ponto['Dia_Semana'] >= 5
        if mask_fds.any():
            tem_entrada_saida = (
                df_ponto.loc[mask_fds, 'Entrada_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].notna()
            )
            
            jornada_total = (df_ponto.loc[mask_fds & tem_entrada_saida, 'Saida_Casa_dt'] - 
                           df_ponto.loc[mask_fds & tem_entrada_saida, 'Entrada_dt']).fillna(zero_delta)
            
            df_ponto.loc[mask_fds & tem_entrada_saida, 'Horas_Extras'] = jornada_total
            
        for col in colunas_calculo:
            df_ponto[col] = pd.to_timedelta(df_ponto[col]).round('s')
        
        # Calcula totais por funcionário
        total_mes = df_ponto.groupby('Nome')[['Total_Faltante', 'Horas_Extras']].sum()
        nomes_disponiveis = df_ponto['Nome'].unique()
        
        return df_ponto, total_mes, nomes_disponiveis
        
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        raise

st.set_page_config(layout="wide", page_title="Calculadora de Ponto", page_icon="⏰")

st.title("🤖 Controle de Horário de Trabalho Automático")
st.write("Faça o upload do arquivo TXT para processar os dados.")

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
         
            detalhe_diario = df_ponto[df_ponto['Nome'] == nome_escolhido].copy()
            
            datas_presente = pd.to_datetime(detalhe_diario['Data_Apenas']).dt.date.unique()
            dias_ausente = []
            
            if len(datas_presente) > 0:
                primeiro_dia = pd.to_datetime(min(datas_presente))
                ultimo_dia = pd.to_datetime(max(datas_presente))
                todos_dias = pd.date_range(start=primeiro_dia, end=ultimo_dia, freq='D')
                dias_uteis_esperados = [dia for dia in todos_dias if dia.dayofweek < 5]
                set_presente = set(datas_presente)
                dias_ausente = [dia for dia in dias_uteis_esperados if dia.date() not in set_presente]

       
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
            
            dias_uteis = detalhe_diario[detalhe_diario['Tipo_Dia'] == 'Dia Útil']
            dias_fds = detalhe_diario[detalhe_diario['Tipo_Dia'] == 'Fim de Semana']
            
            col5, col6 = st.columns(2)
            with col5:
                st.metric(label="Dias Úteis Trabalhados", value=len(dias_uteis))
            with col6:
                st.metric(label="Fins de Semana Trabalhados", value=len(dias_fds))
            
            st.write("---")

        
            st.subheader("🚫 Ausências (Faltas em Dias Úteis)")
            if not dias_ausente:
                st.info("Nenhuma falta (ausência em dia útil) registrada no período.")
            else:
                for dia_falta in dias_ausente:
                    st.warning(f"- {dia_falta.strftime('%Y-%m-%d (%A)')}")

            st.subheader(f"🗓️ Detalhe Diário: {nome_escolhido.upper()}")
         
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
            
            detalhe_exibicao.columns = [
                'Data', 'Dia', 'Tipo', 'Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída',
                'Total Faltante', 'Total Extra', 'Atraso Entrada', 'Saída Ant. Almoço',
                'Atraso Volta', 'Saída Ant.', 'Almoço Excedido'
            ]
            
            st.dataframe(detalhe_exibicao, use_container_width=True)
            
            st.subheader("🔍 Validação dos Cálculos")
            st.write("Selecione um dia para verificar os cálculos detalhados:")
            
            dias_validacao = detalhe_diario['Data_Apenas'].dt.strftime('%Y-%m-%d (%A)').tolist()
            dia_selecionado = st.selectbox("Selecione um dia:", options=dias_validacao)
            
            if dia_selecionado:
            
                data_selecionada = pd.to_datetime(dia_selecionado.split(' ')[0])
                dia_data = detalhe_diario[detalhe_diario['Data_Apenas'] == data_selecionada].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Data:** {data_selecionada.strftime('%Y-%m-%d')}")
                    st.write(f"**Dia da semana:** {dia_data['Nome_Dia']}")
                    st.write(f"**Tipo de dia:** {dia_data['Tipo_Dia']}")
                    st.write(f"**Entrada:** {dia_data['Entrada'].strftime('%H:%M:%S') if pd.notna(dia_data['Entrada']) else '-'}")
                    st.write(f"**Saída Almoço:** {dia_data['Saida_Almoco'].strftime('%H:%M:%S') if pd.notna(dia_data['Saida_Almoco']) else '-'}")
                    st.write(f"**Volta Almoço:** {dia_data['Volta_Almoco'].strftime('%H:%M:%S') if pd.notna(dia_data['Volta_Almoco']) else '-'}")
                    st.write(f"**Saída:** {dia_data['Saida_Casa'].strftime('%H:%M:%S') if pd.notna(dia_data['Saida_Casa']) else '-'}")
                
                with col2:
                    st.write("**Cálculos:**")
                    st.write(f"Total Faltante: {str(dia_data['Total_Faltante']).split()[-1]}")
                    st.write(f"Total Extra: {str(dia_data['Horas_Extras']).split()[-1]}")
                    
                    if dia_data['Tipo_Dia'] == 'Dia Útil':
                        st.write("**Detalhes das Penalidades:**")
                        st.write(f"- Atraso Entrada: {str(dia_data['Atraso_Entrada']).split()[-1]}")
                        st.write(f"- Saída Ant. Almoço: {str(dia_data['Saida_Ant_Almoco']).split()[-1]}")
                        st.write(f"- Atraso Volta: {str(dia_data['Atraso_Volta_Almoco']).split()[-1]}")
                        st.write(f"- Saída Ant.: {str(dia_data['Saida_Ant_Casa']).split()[-1]}")
                        st.write(f"- Almoço Excedido: {str(dia_data['Almoco_Excedido']).split()[-1]}")
                    else:
                        st.write("**Fim de Semana:**")
                        st.write("- Não há penalidades")
                        st.write("- Todo tempo trabalhado é considerado extra")

         
            st.subheader("Baixar Relatórios")
            

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
