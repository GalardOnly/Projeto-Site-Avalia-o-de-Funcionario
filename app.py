# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def formatar_timedelta(td):
    """Formata Timedelta para mostrar horas totais (mesmo acima de 24h)"""
    if pd.isna(td) or td == pd.NaT:
        return "00:00:00"
    
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def processar_folha_ponto(arquivo_carregado):
    try:
        # Lê o arquivo
        df = pd.read_csv(arquivo_carregado, sep='\t', encoding='utf-8')
        
        # VERIFICAÇÃO CRÍTICA: Mostrar estrutura dos dados
        st.write("🔍 **Debug - Estrutura do arquivo:**")
        st.write(f"Total de linhas: {len(df)}")
        st.write(f"Colunas: {df.columns.tolist()}")
        st.write(f"Primeiras linhas:")
        st.dataframe(df.head(3))
        
        # Processamento Inicial
        df['Tempo'] = pd.to_datetime(df['Tempo'], errors='coerce')
        df = df.dropna(subset=['Tempo'])
        df['Data_Apenas'] = df['Tempo'].dt.date
        df = df.sort_values(by=['Tra. No.', 'Data_Apenas', 'Tempo'])
        
        # VERIFICAÇÃO: Mostrar datas únicas
        datas_unicas = df['Data_Apenas'].unique()
        st.write(f"📅 **Datas únicas no arquivo:** {len(datas_unicas)} dias")
        st.write(f"Período: {min(datas_unicas)} a {max(datas_unicas)}")
        
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
        
        # VERIFICAÇÃO: Mostrar distribuição de dias
        st.write("📊 **Distribuição de dias:**")
        st.write(df_ponto['Tipo_Dia'].value_counts())
        
        # Inicializa colunas de timedelta
        zero_delta = pd.Timedelta(0)
        
        # Converte horas para datetime - MÉTODO MAIS SEGURO
        for coluna in colunas_esperadas:
            # Método mais seguro para combinar data e hora
            df_ponto[f'{coluna}_dt'] = df_ponto.apply(
                lambda row: pd.to_datetime(f"{row['Data_Apenas'].strftime('%Y-%m-%d')} {row[coluna]}") 
                if pd.notna(row[coluna]) else pd.NaT,
                axis=1
            )
        
        # Horários esperados
        df_ponto['Esperado_Entrada'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=7, minutes=30)
        df_ponto['Esperado_Saida_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=11, minutes=30)
        df_ponto['Esperado_Volta_Almoco'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=13, minutes=0)
        df_ponto['Esperado_Saida_Casa'] = df_ponto['Data_Apenas'] + pd.Timedelta(hours=17, minutes=50)
        almoco_esperado = pd.Timedelta(minutes=89)
        
        # Inicializa colunas de cálculo
        colunas_calculo = [
            'Atraso_Entrada', 'Saida_Ant_Almoco', 'Atraso_Volta_Almoco', 
            'Saida_Ant_Casa', 'Almoco_Excedido', 'Horas_Extras', 'Total_Faltante'
        ]
        
        for coluna in colunas_calculo:
            df_ponto[coluna] = zero_delta
        
        # Função para calcular diferença positiva
        def calcular_diferenca_positiva(actual, esperado):
            diff = (actual - esperado).fillna(zero_delta)
            diff = pd.to_timedelta(diff)
            return diff.where(diff > zero_delta, zero_delta)
        
        # Dias úteis
        mask_util = df_ponto['Dia_Semana'] < 5
        
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
            
            # Total faltante
            df_ponto.loc[mask_util, 'Total_Faltante'] = (
                df_ponto.loc[mask_util, 'Atraso_Entrada'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Almoco'] + 
                df_ponto.loc[mask_util, 'Atraso_Volta_Almoco'] + 
                df_ponto.loc[mask_util, 'Saida_Ant_Casa'] + 
                df_ponto.loc[mask_util, 'Almoco_Excedido']
            )
        
        # Fins de semana - CÁLCULO COMPLETAMENTE REVISADO E SEGURO
        mask_fds = df_ponto['Dia_Semana'] >= 5
        
        if mask_fds.any():
            st.write("🔍 **Debug - Cálculo Fins de Semana:**")
            
            for idx in df_ponto[mask_fds].index:
                entrada = df_ponto.loc[idx, 'Entrada_dt']
                saida_almoco = df_ponto.loc[idx, 'Saida_Almoco_dt']
                volta_almoco = df_ponto.loc[idx, 'Volta_Almoco_dt']
                saida_casa = df_ponto.loc[idx, 'Saida_Casa_dt']
                data = df_ponto.loc[idx, 'Data_Apenas']
                nome = df_ponto.loc[idx, 'Nome']
                
                horas_trabalhadas = zero_delta
                
                # DEBUG: Mostrar dados brutos
                debug_info = f"{data.strftime('%Y-%m-%d')} - {nome}: "
                debug_info += f"E={entrada}, SA={saida_almoco}, VA={volta_almoco}, S={saida_casa}"
                
                # CENÁRIO 1: Apenas entrada e saída almoço (trabalhou apenas meio período)
                if (pd.notna(entrada) and pd.notna(saida_almoco) and 
                    pd.isna(volta_almoco) and pd.isna(saida_casa)):
                    horas_trabalhadas = saida_almoco - entrada
                    debug_info += f" -> Cenário 1: {horas_trabalhadas}"
                
                # CENÁRIO 2: Apenas entrada e saída (jornada direta sem almoço)
                elif (pd.notna(entrada) and pd.isna(saida_almoco) and 
                      pd.isna(volta_almoco) and pd.notna(saida_casa)):
                    horas_trabalhadas = saida_casa - entrada
                    debug_info += f" -> Cenário 2: {horas_trabalhadas}"
                
                # CENÁRIO 3: Todas as 4 batidas (jornada completa com almoço)
                elif (pd.notna(entrada) and pd.notna(saida_almoco) and 
                      pd.notna(volta_almoco) and pd.notna(saida_casa)):
                    horas_manha = saida_almoco - entrada
                    horas_tarde = saida_casa - volta_almoco
                    horas_trabalhadas = horas_manha + horas_tarde
                    debug_info += f" -> Cenário 3: {horas_trabalhadas} (manhã: {horas_manha}, tarde: {horas_tarde})"
                
                # CENÁRIO 4: Apenas volta almoço e saída (entrou antes do registro)
                elif (pd.isna(entrada) and pd.isna(saida_almoco) and 
                      pd.notna(volta_almoco) and pd.notna(saida_casa)):
                    horas_trabalhadas = saida_casa - volta_almoco
                    debug_info += f" -> Cenário 4: {horas_trabalhadas}"
                
                # CENÁRIO 5: Entrada, saída almoço e volta almoço (sem saída final)
                elif (pd.notna(entrada) and pd.notna(saida_almoco) and 
                      pd.notna(volta_almoco) and pd.isna(saida_casa)):
                    horas_manha = saida_almoco - entrada
                    horas_trabalhadas = horas_manha
                    debug_info += f" -> Cenário 5: {horas_trabalhadas}"
                
                else:
                    debug_info += " -> Nenhum cenário aplicável"
                
                # LIMITE MÁXIMO REALISTA: 10 horas por dia
                if horas_trabalhadas > pd.Timedelta(hours=10):
                    horas_trabalhadas = pd.Timedelta(hours=10)
                    debug_info += f" -> Limitado para {horas_trabalhadas}"
                
                # Garante que não seja negativo
                if horas_trabalhadas > zero_delta:
                    df_ponto.loc[idx, 'Horas_Extras'] = horas_trabalhadas
                    debug_info += f" | Horas Extras: {horas_trabalhadas}"
                else:
                    debug_info += f" | Horas Extras: 0"
                
                # Mostrar debug apenas para os primeiros 5 registros
                if idx < df_ponto[mask_fds].index[0] + 5:
                    st.write(debug_info)
        
        # Converter explicitamente para timedelta
        for col in ['Horas_Extras', 'Total_Faltante']:
            df_ponto[col] = pd.to_timedelta(df_ponto[col])
        
        # Arredonda resultados
        for col in colunas_calculo:
            df_ponto[col] = df_ponto[col].round('s')
        
        # CORREÇÃO: Soma correta das horas extras
        def soma_timedeltas(series):
            total_segundos = series.dt.total_seconds().sum()
            return pd.Timedelta(seconds=total_segundos)
        
        total_mes = df_ponto.groupby('Nome').agg({
            'Total_Faltante': soma_timedeltas,
            'Horas_Extras': soma_timedeltas
        })
        
        nomes_disponiveis = df_ponto['Nome'].unique()
        
        return df_ponto, total_mes, nomes_disponiveis
        
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        import traceback
        st.error(f"Detalhes do erro: {traceback.format_exc()}")
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

        # DEBUG: Mostrar totais por dia para verificação
        with st.expander("🔍 Debug: Verificar cálculo de horas extras por dia"):
            st.write("Horas extras por dia (apenas primeiras linhas):")
            debug_df = df_ponto[['Data_Apenas', 'Nome_Dia', 'Tipo_Dia', 'Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa', 'Horas_Extras']].copy()
            debug_df['Data_Apenas'] = debug_df['Data_Apenas'].dt.strftime('%Y-%m-%d')
            
            # Usar a nova função de formatação
            debug_df['Horas_Extras_Formatado'] = debug_df['Horas_Extras'].apply(formatar_timedelta)
            st.dataframe(debug_df[['Data_Apenas', 'Nome_Dia', 'Tipo_Dia', 'Entrada', 'Saida_Almoco', 'Volta_Almoco', 'Saida_Casa', 'Horas_Extras_Formatado']].head(20))
            
            # Mostrar totais por tipo de dia
            st.write("**Totais por tipo de dia:**")
            totais_por_tipo = df_ponto.groupby('Tipo_Dia')['Horas_Extras'].sum()
            for tipo, total in totais_por_tipo.items():
                st.write(f"{tipo}: {formatar_timedelta(total)}")
            
            # DEBUG ADICIONAL: Mostrar estatísticas dos fins de semana
            fds_df = df_ponto[df_ponto['Tipo_Dia'] == 'Fim de Semana']
            st.write(f"**Estatísticas Fins de Semana:**")
            st.write(f"- Total de dias: {len(fds_df)}")
            if len(fds_df) > 0:
                st.write(f"- Média de horas por dia: {formatar_timedelta(fds_df['Horas_Extras'].mean())}")
                st.write(f"- Máximo de horas em um dia: {formatar_timedelta(fds_df['Horas_Extras'].max())}")
                st.write(f"- Mínimo de horas em um dia: {formatar_timedelta(fds_df['Horas_Extras'].min())}")
                st.write(f"- Soma total: {formatar_timedelta(fds_df['Horas_Extras'].sum())}")

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
                faltante_str = formatar_timedelta(resumo_funcionario['Total_Faltante'])
                st.metric(label="Total Horas Faltantes 🔻", value=faltante_str)
            with col2:
                extras_str = formatar_timedelta(resumo_funcionario['Horas_Extras'])
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
            
            total_horas_extras_manual = detalhe_diario['Horas_Extras'].sum()
            st.write(f"**Verificação:** Soma manual das horas extras: {formatar_timedelta(total_horas_extras_manual)}")
            
            st.write("---")


    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
        import traceback
        st.error(f"Detalhes do erro: {traceback.format_exc()}")
