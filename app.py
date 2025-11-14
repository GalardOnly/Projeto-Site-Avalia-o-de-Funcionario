
import streamlit as st
import pandas as pd
import numpy as np 
import io


def processar_folha_ponto(arquivo_carregado):
    
    # Lê o arquivo
    df = pd.read_csv(arquivo_carregado, sep='\t')
    

    df['Tempo'] = pd.to_datetime(df['Tempo'])
    df['Data_Apenas'] = df['Tempo'].dt.date
    df = df.sort_values(by=['Tra. No.', 'Tempo'])
    df['Batida_Num'] = df.groupby(['Tra. No.', 'Data_Apenas']).cumcount()
    df['Hora'] = df['Tempo'].dt.time
    mapa_batidas = {
        0: 'Entrada', 1: 'Saida_Almoco', 2: 'Volta_Almoco', 3: 'Saida_Casa'
    }
    df['Tipo_Batida'] = df['Batida_Num'].map(mapa_batidas)
    df_ponto = df.pivot_table(
        index=['Tra. No.', 'Nome', 'Data_Apenas'],
        columns='Tipo_Batida', values='Hora', aggfunc='first'
    )
    df_ponto = df_ponto.reset_index()
    df_ponto.columns.name = None
    colunas_finais = ['Tra. No.', 'Nome', 'Data_Apenas', 'Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa']
    colunas_existentes = [coluna for coluna in colunas_finais if coluna in df_ponto.columns]
    df_ponto = df_ponto[colunas_existentes]
    
    #  Conversão para Timestamps
    df_ponto['Data_Apenas'] = pd.to_datetime(df_ponto['Data_Apenas'])
    ts_entrada = pd.to_datetime(df_ponto['Data_Apenas'].astype(str) + ' ' + df_ponto['Entrada'].astype(str), errors='coerce')
    ts_saida_almoco = pd.to_datetime(df_ponto['Data_Apenas'].astype(str) + ' ' + df_ponto['Saida_Almoco'].astype(str), errors='coerce')
    ts_volta_almoco = pd.to_datetime(df_ponto['Data_Apenas'].astype(str) + ' ' + df_ponto['Volta_Almoco'].astype(str), errors='coerce')
    ts_saida_casa = pd.to_datetime(df_ponto['Data_Apenas'].astype(str) + ' ' + df_ponto['Saida_Casa'].astype(str), errors='coerce')

    # Definição das Regras de Horário
    esperado_entrada = df_ponto['Data_Apenas'] + pd.to_timedelta('07:30:00')
    esperado_saida_almoco = df_ponto['Data_Apenas'] + pd.to_timedelta('11:30:00')
    esperado_volta_almoco = df_ponto['Data_Apenas'] + pd.to_timedelta('13:00:00')
    esperado_saida_casa = df_ponto['Data_Apenas'] + pd.to_timedelta('17:50:00')
    almoco_esperado_delta = pd.to_timedelta('89 minutes') # Sua regra de 89 min
    zero_delta = pd.Timedelta(0)

    
    df_ponto['Dia_Semana'] = df_ponto['Data_Apenas'].dt.dayofweek # 0=Seg, 5=Sáb, 6=Dom
    
    atraso_entrada = (ts_entrada - esperado_entrada).fillna(zero_delta).clip(lower=zero_delta)
    saida_ant_almoco = (esperado_saida_almoco - ts_saida_almoco).fillna(zero_delta).clip(lower=zero_delta)
    atraso_volta_almoco = (ts_volta_almoco - esperado_volta_almoco).fillna(zero_delta).clip(lower=zero_delta)
    saida_ant_casa = (esperado_saida_casa - ts_saida_casa).fillna(zero_delta).clip(lower=zero_delta)
    almoco_real_delta_semana = (ts_volta_almoco - ts_saida_almoco).fillna(zero_delta)
    almoco_excedido = (almoco_real_delta_semana - almoco_esperado_delta).fillna(zero_delta).clip(lower=zero_delta)
    
    faltante_semana = atraso_entrada + saida_ant_almoco + atraso_volta_almoco + saida_ant_casa + almoco_excedido
    extra_semana = (ts_saida_casa - esperado_saida_casa).fillna(zero_delta).clip(lower=zero_delta)

    faltante_fds = zero_delta
    penalidade_zero_fds = zero_delta
    
    duracao_manha = (ts_saida_almoco - ts_entrada).fillna(zero_delta).clip(lower=zero_delta)
    duracao_tarde = (ts_saida_casa - ts_volta_almoco).fillna(zero_delta).clip(lower=zero_delta)
    jornada_direta = (ts_saida_casa - ts_entrada).fillna(zero_delta).clip(lower=zero_delta)
    extra_fds = np.where(duracao_manha + duracao_tarde > zero_delta, duracao_manha + duracao_tarde, jornada_direta)

    eh_fds = (df_ponto['Dia_Semana'] >= 5) 

    df_ponto['Total_Faltante_Diario'] = np.where(eh_fds, faltante_fds, faltante_semana)
    df_ponto['Total_Extra_Diario'] = np.where(eh_fds, extra_fds, extra_semana)

    df_ponto['P1_Atraso_Entrada'] = np.where(eh_fds, penalidade_zero_fds, atraso_entrada)
    df_ponto['P2_Saida_Ant_Almoco'] = np.where(eh_fds, penalidade_zero_fds, saida_ant_almoco)
    df_ponto['P3_Atraso_Volta_Almoco'] = np.where(eh_fds, penalidade_zero_fds, atraso_volta_almoco)
    df_ponto['P4_Saida_Ant_Casa'] = np.where(eh_fds, penalidade_zero_fds, saida_ant_casa)
    df_ponto['P5_Almoco_Excedido'] = np.where(eh_fds, penalidade_zero_fds, almoco_excedido)
    
    df_ponto['Horas_Faltantes_Delta'] = df_ponto['Total_Faltante_Diario']
    df_ponto['Horas_Extras_Delta'] = df_ponto['Total_Extra_Diario']

    total_mes = df_ponto.groupby('Nome')[['Horas_Faltantes_Delta', 'Horas_Extras_Delta']].sum()

    total_mes = total_mes.apply(lambda x: x.round('s'))
    
    nomes_disponiveis = df_ponto['Nome'].unique()
    
    return df_ponto, total_mes, nomes_disponiveis

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
            
            detalhe_diario = df_ponto[df_ponto['Nome'] == nome_colhido]
            datas_presente = pd.to_datetime(detalhe_diario['Data_Apenas']).dt.date.unique()
            dias_ausente = [] 
            if len(datas_presente) > 0:
                primeiro_dia = datas_presente.min()
                ultimo_dia = datas_presente.max()
                todos_dias = pd.date_range(start=primeiro_dia, end=ultimo_dia, freq='D')
                dias_uteis_esperados = todos_dias[todos_dias.dayofweek < 5].date
                set_presente = set(datas_presente)
                dias_ausente = [dia for dia in dias_uteis_esperados if dia not in set_presente]

            resumo_funcionario = total_mes.loc[nome_escolhido]
            st.subheader(f"Dashboard de Resumo: {nome_escolhido.upper()}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Horas Faltantes 🔻", value=str(resumo_funcionario['Horas_Faltantes_Delta']))
            with col2:
                st.metric(label="Total Horas Extras 🔺", value=str(resumo_funcionario['Horas_Extras_Delta']))
            with col3:
                st.metric(label="Dias com Ausência (Faltas) 🚫", value=len(dias_ausente))
            st.write("---")

            st.subheader("🚫 Ausências (Faltas em Dias Úteis)")
            if not dias_ausente:
                st.info("Nenhuma falta (ausência em dia útil) registrada no período.")
            else:
                for dia_falta in dias_ausente:
                    st.warning(f"- {dia_falta.strftime('%Y-%m-%d (%A)')}")
            
            st.subheader(f"🗓️ Detalhe Diário (com Penalidades): {nome_escolhido.upper()}")
            
            colunas_detalhe = [
                'Data_Apenas', 'Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa', 
                'Horas_Faltantes_Delta', 'Horas_Extras_Delta',
                'P1_Atraso_Entrada', 'P2_Saida_Ant_Almoco', 'P3_Atraso_Volta_Almoco', 
                'P4_Saida_Ant_Casa', 'P5_Almoco_Excedido'
            ]
            
            detalhe_diario_filtrado = detalhe_diario[colunas_detalhe]
            
            detalhe_diario_formatado = detalhe_diario_filtrado.set_index('Data_Apenas')
            
            colunas_para_arredondar = [
                'Horas_Faltantes_Delta', 'Horas_Extras_Delta',
                'P1_Atraso_Entrada', 'P2_Saida_Ant_Almoco', 'P3_Atraso_Volta_Almoco', 
                'P4_Saida_Ant_Casa', 'P5_Almoco_Excedido'
            ]
            
            for col in colunas_para_arredondar:
                if col in detalhe_diario_formatado.columns:
                    detalhe_diario_formatado[col] = detalhe_diario_formatado[col].round('s')

            detalhe_diario_formatado.rename(columns={
                'Horas_Faltantes_Delta': 'TOTAL FALTANTE',
                'Horas_Extras_Delta': 'TOTAL EXTRA',
                'P1_Atraso_Entrada': 'Penal: Atraso',
                'P2_Saida_Ant_Almoco': 'Penal: Saída Almoço',
                'P3_Atraso_Volta_Almoco': 'Penal: Volta Almoço',
                'P4_Saida_Ant_Casa': 'Penal: Saída Casa',
                'P5_Almoco_Excedido': 'Penal: Almoço Exc.'
            }, inplace=True)
            
            st.dataframe(detalhe_diario_formatado)

            
            st.subheader("Baixar Relatórios")
            csv_completo = df_ponto.to_csv(index=False).encode('utf-8')
            st.download_button(
               label="Baixar Relatório Geral (CSV)",
               data=csv_completo, file_name="relatorio_completo_ponto.csv", mime='text/csv',
            )
            csv_detalhe = detalhe_diario_formatado.to_csv().encode('utf-8')
            st.download_button(
               label=f"Baixar Detalhe - {nome_escolhido} (CSV)",
               data=csv_detalhe, file_name=f"detalhe_{nome_escolhido}.csv", mime='text/csv',
            )
            
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
        st.error("Verifique se o arquivo TXT está no formato correto. Se o erro persistir, cheque os 'Logs' no 'Manage app'.")
