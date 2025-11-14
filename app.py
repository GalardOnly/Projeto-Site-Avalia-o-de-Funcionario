
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
            

            tem_entrada_saida_almoco = (
                df_ponto.loc[mask_fds, 'Entrada_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Almoco_dt'].notna() &
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].isna()
            )

            tem_volta_saida = (
                df_ponto.loc[mask_fds, 'Volta_Almoco_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].notna() &
                df_ponto.loc[mask_fds, 'Entrada_dt'].isna()
            )

            tem_entrada_almoco_volta = (
                df_ponto.loc[mask_fds, 'Entrada_dt'].notna() & 
                df_ponto.loc[mask_fds, 'Saida_Almoco_dt'].notna() &
                df_ponto.loc[mask_fds, 'Volta_Almoco_dt'].notna() &
                df_ponto.loc[mask_fds, 'Saida_Casa_dt'].isna()
            )
            
            if tem_entrada_saida.any():
                jornada_completa = (df_ponto.loc[mask_fds & tem_entrada_saida, 'Saida_Casa_dt'] - 
                                  df_ponto.loc[mask_fds & tem_entrada_saida, 'Entrada_dt']).fillna(zero_delta)
                df_ponto.loc[mask_fds & tem_entrada_saida, 'Horas_Extras'] = jornada_completa
            
            if tem_entrada_saida_almoco.any():
                meio_periodo_manha = (df_ponto.loc[mask_fds & tem_entrada_saida_almoco, 'Saida_Almoco_dt'] - 
                                    df_ponto.loc[mask_fds & tem_entrada_saida_almoco, 'Entrada_dt']).fillna(zero_delta)
                df_ponto.loc[mask_fds & tem_entrada_saida_almoco, 'Horas_Extras'] = meio_periodo_manha
            
            if tem_volta_saida.any():
                meio_periodo_tarde = (df_ponto.loc[mask_fds & tem_volta_saida, 'Saida_Casa_dt'] - 
                                    df_ponto.loc[mask_fds & tem_volta_saida, 'Volta_Almoco_dt']).fillna(zero_delta)
                df_ponto.loc[mask_fds & tem_volta_saida, 'Horas_Extras'] = meio_periodo_tarde
            
           
            if tem_entrada_almoco_volta.any():
                periodo_manha = (df_ponto.loc[mask_fds & tem_entrada_almoco_volta, 'Saida_Almoco_dt'] - 
                               df_ponto.loc[mask_fds & tem_entrada_almoco_volta, 'Entrada_dt']).fillna(zero_delta)
              
                df_ponto.loc[mask_fds & tem_entrada_almoco_volta, 'Horas_Extras'] = periodo_manha
            
        for col in colunas_calculo:
            df_ponto[col] = pd.to_timedelta(df_ponto[col]).round('s')
        
        total_mes = df_ponto.groupby('Nome')[['Total_Faltante', 'Horas_Extras']].sum()
        nomes_disponiveis = df_ponto['Nome'].unique()
        
        return df_ponto, total_mes, nomes_disponiveis
        
    except Exception as e:
        st.error(f"Erro no processamento: {str(e)}")
        raise

# O resto do código da interface permanece igual...
# [A interface Streamlit continua exatamente como antes]
