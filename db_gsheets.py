import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import time

# Scopes needed for Google Sheets and Google Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def get_gcp_credentials():
    return Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)

@st.cache_resource
def get_gspread_client():
    creds = get_gcp_credentials()
    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_gspread_client()
    # O nome da planilha é "arvoredo341" conforme print do usuário
    return client.open("arvoredo341")

def init_db():
    sh = get_spreadsheet()
    
    # Garantir que as abas existem. Se não existirem (erro ao abrir), cria.
    try:
        ws_historico = sh.worksheet("historico")
    except gspread.exceptions.WorksheetNotFound:
        ws_historico = sh.add_worksheet(title="historico", rows="1000", cols="20")
        
    try:
        ws_contrato = sh.worksheet("tabela_contrato")
    except gspread.exceptions.WorksheetNotFound:
        ws_contrato = sh.add_worksheet(title="tabela_contrato", rows="10", cols="10")
        
    try:
        ws_caucao = sh.worksheet("tabela_caucao_historico")
    except gspread.exceptions.WorksheetNotFound:
        ws_caucao = sh.add_worksheet(title="tabela_caucao_historico", rows="100", cols="10")

    # Iniciar cabeçalhos se não existirem
    if ws_historico.acell('A1').value != "id":
        ws_historico.insert_row(["id", "mes_referencia", "vencimento", "data_pagamento", "status", "dias_atraso", "total_variaveis", "situacao", "anexo", "nome_anexo"], 1)
        
    if ws_contrato.acell('A1').value != "id":
        ws_contrato.insert_row(["id", "inquilina", "valor_aluguel", "bonus_pontualidade", "percentual_multa", "caucao_inicial", "data_inicio"], 1)
        
    if ws_caucao.acell('A1').value != "id":
        ws_caucao.insert_row(["id", "data_atualizacao", "indice_percentual", "valor_atualizado"], 1)

def load_data():
    sh = get_spreadsheet()
    ws = sh.worksheet("historico")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if not df.empty:
        # Tenta ordenar e preencher
        df = df.sort_values(by="vencimento", ascending=True)
    return df

def load_contrato():
    sh = get_spreadsheet()
    ws = sh.worksheet("tabela_contrato")
    records = ws.get_all_records()
    if records:
        row = records[0] # Consideramos que o ID=1 está na primeira linha de dados
        return {
            "inquilina": str(row.get("inquilina", "")),
            "valor_aluguel": float(row.get("valor_aluguel", 0)),
            "bonus_pontualidade": float(row.get("bonus_pontualidade", 0)),
            "percentual_multa": float(row.get("percentual_multa", 0)),
            "caucao_inicial": float(row.get("caucao_inicial", 0)),
            "data_inicio": str(row.get("data_inicio", ""))
        }
    return None

def load_caucao():
    sh = get_spreadsheet()
    ws = sh.worksheet("tabela_caucao_historico")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    return df

def _get_next_id(ws):
    records = ws.get_all_records()
    if not records:
        return 1
    # Pega o maior id existente e soma 1
    ids = [int(r.get("id", 0)) for r in records if str(r.get("id", "")).isdigit()]
    return max(ids) + 1 if ids else 1

def insert_fatura(mes_referencia, vencimento, status, dias_atraso, total_variaveis, situacao, anexo_url, nome_anexo):
    sh = get_spreadsheet()
    ws = sh.worksheet("historico")
    novo_id = _get_next_id(ws)
    
    nova_linha = [
        novo_id,
        mes_referencia,
        str(vencimento),
        "", # data_pagamento vazia inicialmente
        status,
        dias_atraso,
        total_variaveis,
        situacao,
        anexo_url if anexo_url else "",
        nome_anexo if nome_anexo else ""
    ]
    ws.append_row(nova_linha)
    
def get_fatura_row_index(fatura_id):
    sh = get_spreadsheet()
    ws = sh.worksheet("historico")
    col_ids = ws.col_values(1) # Primeira coluna é o ID
    try:
        # +1 porque no gspread o index é 1-based, e a lista col_values tem índice 0
        return col_ids.index(str(fatura_id)) + 1 
    except ValueError:
        return None

def update_pagamento(fatura_id, data_pagamento, dias_atraso, status, situacao):
    idx = get_fatura_row_index(fatura_id)
    if idx:
        sh = get_spreadsheet()
        ws = sh.worksheet("historico")
        # As colunas são: 1=id, 2=mes, 3=venc, 4=data_pag, 5=status, 6=dias_atraso, 7=tot_var, 8=situacao
        ws.update_cell(idx, 4, str(data_pagamento))
        ws.update_cell(idx, 5, status)
        ws.update_cell(idx, 6, dias_atraso)
        ws.update_cell(idx, 8, situacao)

def delete_fatura(fatura_id):
    idx = get_fatura_row_index(fatura_id)
    if idx:
        sh = get_spreadsheet()
        ws = sh.worksheet("historico")
        ws.delete_rows(idx)

def update_fatura(fatura_id, mes_referencia, vencimento, total_variaveis, data_pagamento, status, dias_atraso, situacao):
    idx = get_fatura_row_index(fatura_id)
    if idx:
        sh = get_spreadsheet()
        ws = sh.worksheet("historico")
        # Update múltiplo para otimizar requisições
        updates = [
            {'range': f'B{idx}', 'values': [[str(mes_referencia)]]},
            {'range': f'C{idx}', 'values': [[str(vencimento)]]},
            {'range': f'D{idx}', 'values': [[str(data_pagamento) if data_pagamento else ""]]},
            {'range': f'E{idx}', 'values': [[str(status)]]},
            {'range': f'F{idx}', 'values': [[dias_atraso]]},
            {'range': f'G{idx}', 'values': [[total_variaveis]]},
            {'range': f'H{idx}', 'values': [[str(situacao)]]},
        ]
        ws.batch_update(updates)

def save_contrato(inquilina, valor_aluguel, bonus_pontualidade, percentual_multa, caucao_inicial, data_inicio):
    sh = get_spreadsheet()
    ws = sh.worksheet("tabela_contrato")
    records = ws.get_all_records()
    
    linha_dados = [
        1,
        inquilina,
        valor_aluguel,
        bonus_pontualidade,
        percentual_multa,
        caucao_inicial,
        str(data_inicio)
    ]
    
    if records:
        # Update primeira linha de dados (row 2)
        ws.update('A2:G2', [linha_dados])
    else:
        ws.append_row(linha_dados)

def insert_caucao(data_atualizacao, indice_percentual, valor_atualizado):
    sh = get_spreadsheet()
    ws = sh.worksheet("tabela_caucao_historico")
    novo_id = _get_next_id(ws)
    
    nova_linha = [
        novo_id,
        str(data_atualizacao),
        indice_percentual,
        valor_atualizado
    ]
    ws.append_row(nova_linha)

def check_fatura_exists(mes_referencia):
    sh = get_spreadsheet()
    ws = sh.worksheet("historico")
    col_mes = ws.col_values(2) # Coluna 2 é mes_referencia
    return str(mes_referencia) in col_mes

# ==========================================
# INTEGRAÇÃO COM GOOGLE DRIVE (UPLOADS)
# ==========================================
def upload_to_drive(file_bytes, filename):
    try:
        creds = get_gcp_credentials()
        service = build('drive', 'v3', credentials=creds)
        
        # Procurar a pasta "app"
        results = service.files().list(q="mimeType='application/vnd.google-apps.folder' and name='app'", spaces='drive').execute()
        folders = results.get('files', [])
        
        file_metadata = {'name': filename}
        if folders:
            folder_id = folders[0]['id']
            file_metadata['parents'] = [folder_id]
            
        # resumable=False é mais seguro para arquivos pequenos em ambientes Serverless
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='application/octet-stream', resumable=False)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        
        # Tornar visível para qualquer pessoa com o link
        try:
            service.permissions().create(fileId=file.get('id'), body={'type': 'anyone', 'role': 'reader'}).execute()
        except Exception as e:
            pass # Ignora se não puder alterar permissões
            
        return file.get('webViewLink')
    except Exception as e:
        import streamlit as st
        # Captura e exibe o erro real do Google (ex: permissão negada)
        error_msg = str(e)
        if hasattr(e, 'reason'):
            error_msg = f"{e.reason} - {error_msg}"
        st.error(f"**Falha ao enviar arquivo para o Google Drive.**\n\nDetalhes do erro do Google: `{error_msg}`")
        st.stop()
