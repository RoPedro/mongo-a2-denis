# ==========================================
# ETAPA 4: ETL FINAL - CORREÇÃO DE AGRUPAMENTO DO RJ
# ==========================================
import pandas as pd
from IPython.display import display

# Variável global
df_final_global = None

def limpar_valor_numerico(valor):
    """Auxiliar: Transforma '12,5' (string) em 12.5 (float)"""
    if valor is None: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    try:
        return float(str(valor).replace(',', '.'))
    except:
        return 0.0

def encontrar_coluna_por_padrao(dataframe, padroes):
    for col_real in dataframe.columns:
        for padrao in padroes:
            if padrao.lower() in col_real.lower():
                return col_real
    return None

def executar_etl():
    global df_final_global

    # Configuração de exibição
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)

    print("--- 1. EXTRAÇÃO: Baixando dados do MongoDB Atlas... ---")

    col_dengue = get_mongo_collection("casos_dengue")
    col_chuva = get_mongo_collection("precipitacao_chuva")

    if col_dengue is None or col_chuva is None:
        print("❌ Erro de conexão.")
        return

    df_dengue = pd.DataFrame(list(col_dengue.find({}, {"_id": 0})))
    df_chuva = pd.DataFrame(list(col_chuva.find({}, {"_id": 0})))

    if df_dengue.empty or df_chuva.empty:
        print("❌ Erro: Tabelas vazias.")
        return None

    print(f"   -> Registros extraídos (Total Bruto): Dengue={len(df_dengue)} | Chuva={len(df_chuva)}")
    print("\n--- 2. TRANSFORMAÇÃO (Normalização do RJ) ---")

    # ====================================================
    # TRATAMENTO DA DENGUE
    # ====================================================
    col_data_dengue = encontrar_coluna_por_padrao(df_dengue, ['data_inise', 'dt_notific', 'data', 'dt_sin_pri'])
    if not col_data_dengue: col_data_dengue = df_dengue.columns[0]

    df_dengue['data_obj'] = pd.to_datetime(df_dengue[col_data_dengue], errors='coerce')

    # Filtro 2024
    df_dengue = df_dengue[df_dengue['data_obj'].dt.year == 2024].copy()

    df_dengue['casos'] = pd.to_numeric(df_dengue['casos'], errors='coerce').fillna(0)
    df_dengue['mes_ano'] = df_dengue['data_obj'].dt.to_period('M')
    df_dengue['municipio'] = df_dengue['municipio'].astype(str).str.upper().str.strip()

    # Agregação
    dengue_mensal = df_dengue.groupby(['municipio', 'mes_ano'])['casos'].sum().reset_index()
    dengue_mensal = dengue_mensal.sort_values(['mes_ano', 'municipio'])

    print("\n--- [PLANILHA 1] Dados de Dengue (Ordenado por Mês) ---")
    cols_dengue_view = ['mes_ano', 'municipio', 'casos']
    display(dengue_mensal[cols_dengue_view])

    # ====================================================
    # TRATAMENTO DA CHUVA (COM CORREÇÃO DO RIO DE JANEIRO)
    # ====================================================
    col_chuva_valor = encontrar_coluna_por_padrao(df_chuva, ['precipita', 'total', 'chuva', 'mm'])
    if not col_chuva_valor: col_chuva_valor = df_chuva.columns[1]

    col_data_chuva = encontrar_coluna_por_padrao(df_chuva, ['data_medicao', 'data', 'dt_medicao'])
    if not col_data_chuva: col_data_chuva = 'data_medicao'

    df_chuva['chuva_tratada'] = df_chuva[col_chuva_valor].apply(limpar_valor_numerico)
    df_chuva['data_obj'] = pd.to_datetime(df_chuva[col_data_chuva], errors='coerce')

    # Filtro 2024
    df_chuva = df_chuva[df_chuva['data_obj'].dt.year == 2024].copy()

    df_chuva['mes_ano'] = df_chuva['data_obj'].dt.to_period('M')
    df_chuva['municipio'] = df_chuva['municipio'].astype(str).str.upper().str.strip()

    # --- CORREÇÃO DO RIO DE JANEIRO ---
    # Transforma "RIO DE JANEIRO - JACAREPAGUA", "RIO DE JANEIRO - FORTE...", etc em "RIO DE JANEIRO"
    # Assim, o groupby abaixo vai somar todos eles num único registro.
    filtro_rj = df_chuva['municipio'].str.startswith('RIO DE JANEIRO')
    df_chuva.loc[filtro_rj, 'municipio'] = 'RIO DE JANEIRO'

    # Agregação (Agora o RJ será somado corretamente)
    chuva_mensal = df_chuva.groupby(['municipio', 'mes_ano'])['chuva_tratada'].sum().reset_index()
    chuva_mensal.rename(columns={'chuva_tratada': 'precipitacao'}, inplace=True)
    chuva_mensal = chuva_mensal.sort_values(['mes_ano', 'municipio'])

    print("\n--- [PLANILHA 2] Dados de Chuva (Ordenado por Mês - RJ Unificado) ---")
    cols_chuva_view = ['mes_ano', 'municipio', 'precipitacao']
    display(chuva_mensal[cols_chuva_view])

    # ====================================================
    # INTEGRAÇÃO (MERGE)
    # ====================================================
    print("\n--- 3. INTEGRAÇÃO ---")
    df_final = pd.merge(dengue_mensal, chuva_mensal, on=['municipio', 'mes_ano'], how='inner')

    df_final['mes_ref'] = df_final['mes_ano'].astype(str)
    df_final['mes_num'] = df_final['mes_ano'].dt.month

    # Ordenação final
    df_final = df_final.sort_values(['mes_ano', 'municipio'])
    df_final_global = df_final

    print("\n--- [PLANILHA 3] Dataset Final Consolidado (Ordenado por Mês) ---")
    cols_final_view = ['mes_ano', 'municipio', 'casos', 'precipitacao']
    display(df_final[cols_final_view])

    return df_final

if __name__ == "__main__":
    executar_etl()
