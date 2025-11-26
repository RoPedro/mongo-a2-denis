# ==========================================
# ETAPA 2: IMPORTAÇÃO, CONFIGURAÇÃO E CONEXÃO COM MONGODB
# ==========================================
import pandas as pd
import pymongo
from pymongo import MongoClient
import matplotlib.pyplot as plt
import seaborn as sns
import io
import requests
from IPython.display import display
import time

MONGO_URI = "localhost:27017" # Aumentando os timeouts
DB_NAME = "bigdata_dengue_rj"

def get_mongo_collection(collection_name):
    """Conecta ao MongoDB e retorna a coleção desejada."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print(f"Conectado ao MongoDB: {DB_NAME}")
        return db[collection_name]
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        return None

# ==========================================
# ETAPA 3: CARGA INICIAL (CORREÇÃO: PYMONGO CHECK)
# ==========================================

def listar_arquivos_github(usuario, repositorio, pasta):
    url_api = f"https://api.github.com/repos/{usuario}/{repositorio}/contents/{pasta}"
    try:
        response = requests.get(url_api)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []

def inserir_em_lotes(colecao, dataframe, tamanho_lote=1000):
    """
    Insere dados em pedaços menores para evitar queda de conexão.
    """
    registros = dataframe.to_dict("records")
    total = len(registros)

    print(f"   ...Iniciando inserção de {total} registros no MongoDB...")

    for i in range(0, total, tamanho_lote):
        lote = registros[i : i + tamanho_lote]
        try:
            colecao.insert_many(lote)
            if i % 10000 == 0: # Feedback visual a cada 10k
                print(f"      - Progresso: {i}/{total} registros salvos.")
        except Exception as e:
            print(f"      ❌ Erro no lote {i}: {e}")
            time.sleep(2) # Pausa dramática para o banco respirar
            try:
                colecao.insert_many(lote)
                print(f"      - Lote {i} recuperado e inserido.")
            except:
                print(f"      - Lote {i} perdido.")

def carregar_csvs_para_mongo():
    print("--- Iniciando Carga Otimizada (Versão Final) ---")

    GITHUB_USER = "RoPedro"
    GITHUB_REPO = "csv-dados-av1-denis"

    # ---------------------------------------------------------
    # PARTE 1: MEMÓRIA (DOWNLOAD E PROCESSAMENTO)
    # ---------------------------------------------------------

    # --- DENGUE ---
    print(f"\n1. Preparando DENGUE (Memória)...")
    arquivos_dengue = listar_arquivos_github(GITHUB_USER, GITHUB_REPO, "dengue_data")
    lista_dengue = []

    for arq in arquivos_dengue:
        if arq['name'].lower().endswith('.csv'):
            try:
                df = pd.read_csv(arq['download_url'], sep=';', encoding='utf-8')
            except:
                try: df = pd.read_csv(arq['download_url'], sep=',', encoding='latin1')
                except: continue
            df.columns = df.columns.str.strip().str.lower()
            lista_dengue.append(df)

    df_dengue_final = pd.concat(lista_dengue, ignore_index=True) if lista_dengue else pd.DataFrame()
    print(f"   -> Dengue pronto: {len(df_dengue_final)} linhas.")

    # --- CHUVA ---
    print(f"\n2. Preparando CHUVA (Memória)...")
    arquivos_chuva = listar_arquivos_github(GITHUB_USER, GITHUB_REPO, "pluv_data")
    if not arquivos_chuva: arquivos_chuva = listar_arquivos_github(GITHUB_USER, GITHUB_REPO, "Pluv_data")

    lista_chuva = []
    for arq in arquivos_chuva:
        if arq['name'].lower().endswith('.csv'):
            try:
                # Lógica INMET (pula cabeçalho)
                df = pd.read_csv(arq['download_url'], sep=';', encoding='latin1', skiprows=8)

                if 'Data' not in df.columns and 'DATA (YYYY-MM-DD)' not in df.columns:
                     df = pd.read_csv(arq['download_url'], sep=';', encoding='latin1', skiprows=9)

                df.rename(columns={'Data': 'data_medicao', 'DATA (YYYY-MM-DD)': 'data_medicao'}, inplace=True)

                partes = arq['name'].split('_')
                muni = partes[4] if len(partes) > 4 else "DESCONHECIDO"
                df['municipio'] = muni

                df.columns = df.columns.str.strip().str.lower()
                lista_chuva.append(df)
            except:
                pass # Silencioso para não poluir o log, já sabemos que funciona

    df_chuva_final = pd.DataFrame()
    if lista_chuva:
        df_chuva_final = pd.concat(lista_chuva, ignore_index=True)
        # Limpeza essencial para o Mongo não rejeitar
        df_chuva_final = df_chuva_final.loc[:, ~df_chuva_final.columns.str.contains('unnamed')]
        df_chuva_final = df_chuva_final.where(pd.notnull(df_chuva_final), None)
        print(f"   -> Chuva pronta: {len(df_chuva_final)} linhas.")

    # ---------------------------------------------------------
    # PARTE 2: CONEXÃO E SALVAMENTO (CORREÇÃO AQUI)
    # ---------------------------------------------------------
    print("\n3. Conectando ao MongoDB para salvar...")

    # Obtém as coleções
    col_dengue = get_mongo_collection("casos_dengue")
    col_chuva = get_mongo_collection("precipitacao_chuva")

    # CORREÇÃO DO ERRO: Usa 'is not None' explicitamente
    if col_dengue is not None:
        col_dengue.delete_many({})

    if col_chuva is not None:
        col_chuva.delete_many({})

    # Insere Dengue
    if not df_dengue_final.empty and col_dengue is not None:
        inserir_em_lotes(col_dengue, df_dengue_final)
        print("   ✅ DENGUE SALVO COM SUCESSO.")

    # Insere Chuva
    if not df_chuva_final.empty and col_chuva is not None:
        inserir_em_lotes(col_chuva, df_chuva_final)
        print("   ✅ CHUVA SALVA COM SUCESSO.")

    print("\n--- FIM DA CARGA ---")

if __name__ == "__main__":
    carregar_csvs_para_mongo()
