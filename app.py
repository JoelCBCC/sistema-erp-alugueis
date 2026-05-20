import streamlit as st
import pandas as pd
import db_gsheets as db
import time
from datetime import date, timedelta

# Configuração da página - Deve ser a primeira chamada do Streamlit
st.set_page_config(
    page_title="Cálculo de Aluguéis",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.dialog("Sobre o Sistema")
def modal_sobre():
    st.image("https://cdn-icons-png.flaticon.com/512/3204/3204094.png", width=80)
    st.markdown("### ERP Automático de Aluguéis")
    st.markdown("**Versão:** 1.0.0")
    st.markdown("**Desenvolvedor:** Joel Luciano")
    st.markdown("---")
    st.markdown("*(O texto completo descrevendo os detalhes do programa, história ou instruções será inserido aqui posteriormente)*")
    
    if st.button("OK / Voltar", type="primary", use_container_width=True):
        st.rerun()

if 'confirmar_duplicado' not in st.session_state:
    st.session_state.confirmar_duplicado = False
if 'dados_temporarios' not in st.session_state:
    st.session_state.dados_temporarios = {}
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'telefone_vinculo' not in st.session_state:
    st.session_state.telefone_vinculo = None

# ==========================================
# SETUP DO BANCO DE DADOS (Google Sheets)
# ==========================================
# Inicializa o banco (com cache para não deixar o sistema lento a cada clique)
@st.cache_data
def run_init_db_once():
    db.init_db()

run_init_db_once()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center;'>🏢 Acesso Restrito</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Insira suas credenciais para acessar o ERP Imobiliário.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_login"):
            usuario_input = st.text_input("Usuário")
            senha_input = st.text_input("Senha", type="password")
            submit_login = st.form_submit_button("Entrar")
            
            if submit_login:
                user_data = db.authenticate_user(usuario_input, senha_input)
                if user_data:
                    st.session_state.autenticado = True
                    st.session_state.role = user_data["role"]
                    st.session_state.telefone_vinculo = str(user_data.get("telefone_vinculo", ""))
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# ==========================================
# FUNÇÕES DE CARREGAMENTO (Inversão de Controle)
# ==========================================
def load_data():
    return db.load_data()

def load_contrato():
    return db.load_contrato()

def load_caucao():
    return db.load_caucao()

def format_currency(value):
    """Formata valor float para moeda local (pt-BR)."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# TÍTULO PRINCIPAL
# ==========================================
st.title("🏢 Sistema de Cálculo Automático de Aluguéis")
st.markdown("Bem-vindo ao sistema inteligente de gestão de contratos e faturas.")
st.markdown("---")

# Carega o contrato ativo
contrato_atual = load_contrato()

# ==========================================
# PAINEL DO INQUILINO (PORTAL DO CLIENTE)
# ==========================================
if st.session_state.role == "Inquilino":
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    st.title("🏢 Meu Painel - Área do Cliente")
    st.markdown("---")
    
    if not contrato_atual or str(contrato_atual.get("telefone", "")).strip() != str(st.session_state.telefone_vinculo).strip():
        st.warning("Nenhum contrato ativo encontrado para o seu usuário (telefone não vinculado).")
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()
        st.stop()
        
    st.write(f"### Olá, {contrato_atual['inquilina']}!")
    
    df_historico = load_data()
    faturas_abertas = df_historico[df_historico["situacao"] == "Aberta"] if not df_historico.empty else pd.DataFrame()
    
    if faturas_abertas.empty:
        st.success("✅ SEM FATURA EM ABERTO")
    else:
        if len(faturas_abertas) == 1:
            fat = faturas_abertas.iloc[0]
            # Calcula valor base + variaveis do historico
            val_total = float(contrato_atual['valor_aluguel']) + float(fat['total_variaveis'] or 0)
            st.warning(f"⚠️ **Fatura em Aberto**")
            st.write(f"**Vencimento:** {fat['vencimento']} | **Valor Total (com aluguel base):** R$ {format_currency(val_total)}")
            if str(fat['anexo']).startswith("http"):
                st.markdown(f"[📥 Baixar Fatura (PDF)]({fat['anexo']})")
        else:
            st.error("🚨 HÁ MAIS DE UMA FATURA EM ABERTO")
            
    st.markdown("---")
    st.markdown("#### Meu Histórico de Faturas")
    if not df_historico.empty:
        df_exibicao = df_historico[["mes_referencia", "vencimento", "status", "dias_atraso", "situacao", "anexo"]]
        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
        
    st.markdown("---")
    if st.button("Sair do Sistema"):
        st.session_state.autenticado = False
        st.rerun()
    st.stop()

# ==========================================
# BARRA LATERAL (SIDEBAR) - Visão Admin
# ==========================================
st.sidebar.success(f"Logado como: {st.session_state.role}")
if st.sidebar.button("Sair do Sistema", use_container_width=True):
    st.session_state.autenticado = False
    st.rerun()
    
if st.sidebar.button("ℹ️ Sobre o Sistema", use_container_width=True):
    modal_sobre()
    
st.sidebar.markdown("---")

st.sidebar.header("⚙️ Parâmetros do Contrato")

if contrato_atual:
    # Se o contrato existe, injetamos nas variáveis que a regra de negócio do faturamento usa
    valor_base = contrato_atual["valor_aluguel"]
    desconto_pontualidade = contrato_atual["bonus_pontualidade"]
    percentual_multa = contrato_atual["percentual_multa"]
    
    # Exibe as métricas de forma visual (read-only)
    st.sidebar.metric("Inquilina(o)", contrato_atual["inquilina"])
    st.sidebar.metric("Aluguel Bruto", format_currency(valor_base))
    st.sidebar.metric("Desconto (Pontualidade)", format_currency(desconto_pontualidade))
    st.sidebar.metric("Multa ao Dia", f"{percentual_multa:.2f}%")
else:
    st.sidebar.warning("⚠️ Nenhum contrato configurado. Por favor, acesse a aba 'Contrato & Caução' para inicializar o sistema.")
    valor_base = 0.0
    desconto_pontualidade = 0.0
    percentual_multa = 0.0

st.sidebar.markdown("---")
st.sidebar.header("📝 Gerar Nova Fatura")

with st.sidebar.form("form_nova_fatura"):
    novo_mes = st.text_input("Mês de Referência", placeholder="ex: 05/2026")
    novo_vencimento = st.date_input("Data de Vencimento")
    
    with st.expander("➕ Gastos Variáveis do Mês"):
        lista_variaveis = [
            "Consumo de gás", "Uso de Churrasqueira", "Locação de vaga de garagem", 
            "Uso do salão de festas", "Fundo de reserva", "Taxa do condomínio", 
            "Fundo p/ Férias e 13º Salário", "Diversos", "Taxa de coleta de Lixo", "IPTU"
        ]
        
        total_variaveis = 0.0
        for item in lista_variaveis:
            col_check, col_valor = st.columns([1, 2])
            with col_check:
                cobrar = st.checkbox("Cobrar?", key=f"chk_{item}")
            with col_valor:
                valor_item = st.number_input(item, min_value=0.0, step=10.0, format="%.2f", key=f"val_{item}")
                
            if cobrar:
                total_variaveis += valor_item

    arquivo_upado = st.file_uploader("Anexar Documento (Opcional)", key="novo_anexo")
    submit_btn = st.form_submit_button("Gerar Fatura")

    if submit_btn:
        if not contrato_atual:
            st.error("⚠️ Configure o contrato antes de gerar faturas!")
        elif novo_mes.strip() != "":
            anexo_url = ""
            nome_anexo = ""
            if arquivo_upado is not None:
                anexo_bytes = arquivo_upado.read()
                nome_anexo = arquivo_upado.name
                with st.spinner("Enviando anexo para a nuvem..."):
                    anexo_url = db.upload_to_gcs(anexo_bytes, nome_anexo)
                
            if db.check_fatura_exists(novo_mes) and not st.session_state.confirmar_duplicado:
                st.session_state.confirmar_duplicado = True
                st.session_state.dados_temporarios = {
                    'novo_mes': novo_mes,
                    'novo_vencimento': novo_vencimento,
                    'total_variaveis': total_variaveis,
                    'anexo_url': anexo_url,
                    'nome_anexo': nome_anexo
                }
                st.rerun()
            else:
                with st.spinner("Gerando fatura na planilha..."):
                    db.insert_fatura(novo_mes, novo_vencimento, "Aguardando", 0, total_variaveis, "Aberta", anexo_url, nome_anexo)
                st.session_state.confirmar_duplicado = False
                st.success("Fatura gerada com sucesso!")
                time.sleep(1)
                st.rerun()
        else:
            st.error("O campo 'Mês de Referência' é obrigatório!")
    st.markdown("---")
    
# ==========================================
# ABAS DO SISTEMA (TABS)
# ==========================================
tab_faturamento, tab_contrato, tab_usuarios = st.tabs(["🧾 Faturamento & Histórico", "📜 Contrato & Caução", "👥 Gestão de Usuários"])

# ==========================================
# ABA 1: FATURAMENTO E HISTÓRICO
# ==========================================
with tab_faturamento:
    if st.session_state.confirmar_duplicado:
        mes_referencia_salvo = st.session_state.dados_temporarios.get('novo_mes', '')
        st.warning(f"⚠️ Já existe uma fatura para esse inquilino em {mes_referencia_salvo}, deseja prosseguir?")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Sim, Prosseguir", type="primary"):
                dados = st.session_state.dados_temporarios
                with st.spinner("Inserindo fatura..."):
                    db.insert_fatura(dados['novo_mes'], dados['novo_vencimento'], "Aguardando", 0, dados['total_variaveis'], "Aberta", dados['anexo_url'], dados['nome_anexo'])
                st.session_state.confirmar_duplicado = False
                st.rerun()
        with col_btn2:
            if st.button("Cancelar"):
                st.session_state.confirmar_duplicado = False
                st.rerun()

    if not contrato_atual:
        st.info("👈 Use a aba 'Contrato & Caução' para configurar o sistema antes de gerar faturas.")
    else:
        df_historico = load_data()
        
        if df_historico.empty:
            st.info("Nenhum registro encontrado no banco de dados. Use a barra lateral para gerar a primeira fatura.")
        else:
            # A análise para a "Próxima Fatura" é baseada no mês anterior
            ultimo_mes = df_historico.iloc[-1]
            status_anterior = ultimo_mes["status"]
            atraso_anterior = ultimo_mes["dias_atraso"]
            
            desconto_aplicado = 0.0
            encargos = 0.0
            
            if status_anterior == "No Prazo":
                desconto_aplicado = desconto_pontualidade
            elif status_anterior == "Em Atraso":
                encargos = valor_base * (percentual_multa / 100) * atraso_anterior
            
            valor_total = valor_base - desconto_aplicado + encargos + total_variaveis
            
            st.subheader("📊 Geração da Próxima Fatura")
            
            if status_anterior == "No Prazo":
                st.success(f"O mês anterior ({ultimo_mes['mes_referencia']}) foi pago no prazo. O Desconto de Pontualidade será aplicado!")
            elif status_anterior == "Em Atraso":
                st.error(f"O mês anterior ({ultimo_mes['mes_referencia']}) foi pago com atraso. Desconto de pontualidade revogado e encargos adicionados.")
            else:
                st.warning(f"O mês anterior ({ultimo_mes['mes_referencia']}) ainda está aguardando pagamento. Nenhuma multa aplicada ainda.")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.metric("Aluguel Bruto", format_currency(valor_base))
            with col2: st.metric("Desconto Aplicado", format_currency(desconto_aplicado), delta="Concedido" if desconto_aplicado > 0 else "Perdido/Indisponível", delta_color="normal" if desconto_aplicado > 0 else "inverse")
            with col3: st.metric("Encargos do Mês Anterior", format_currency(encargos), delta=f"{atraso_anterior} dias" if encargos > 0 else "Sem multas", delta_color="inverse" if encargos > 0 else "off")
            with col4: st.metric("Total de Variáveis", format_currency(total_variaveis), delta="Itens Adicionais", delta_color="off")
            with col5: st.metric("Total a Pagar", format_currency(valor_total), delta="Com desconto" if desconto_aplicado > 0 else "Com encargos", delta_color="normal" if desconto_aplicado > 0 else "inverse")
            
            st.markdown("---")
            st.subheader("🗓️ Contas a Receber & Histórico")
            
            df_exibicao = df_historico[["mes_referencia", "vencimento", "data_pagamento", "situacao", "status", "dias_atraso", "total_variaveis"]]
            
            event = st.dataframe(
                df_exibicao, 
                on_select='rerun', 
                selection_mode='single-row', 
                use_container_width=True, 
                hide_index=True
            )
            
            # Master-Detail: Dar Baixa / Detalhes
            if len(event.selection.rows) > 0:
                selected_idx = event.selection.rows[0]
                linha_selecionada = df_historico.iloc[selected_idx]
                
                row_id = int(linha_selecionada["id"])
                situacao_selecionada = linha_selecionada.get("situacao", "Aberta")
                mes_selecionado = linha_selecionada["mes_referencia"]
                historico_variaveis = linha_selecionada.get("total_variaveis", 0.0)
                
                detalhe_desconto = 0.0
                detalhe_encargos = 0.0
                
                if selected_idx > 0:
                    linha_anterior = df_historico.iloc[selected_idx - 1]
                    if linha_anterior["status"] == "No Prazo":
                        detalhe_desconto = desconto_pontualidade
                    elif linha_anterior["status"] == "Em Atraso":
                        detalhe_encargos = valor_base * (percentual_multa / 100) * linha_anterior["dias_atraso"]
                        
                total_fatura = valor_base - detalhe_desconto + detalhe_encargos + historico_variaveis
                
                st.markdown("---")
                st.subheader(f"🔎 Detalhamento da Fatura: {mes_selecionado}")
                
                d_col1, d_col2, d_col3, d_col4 = st.columns(4)
                with d_col1: st.metric("Aluguel Bruto", format_currency(valor_base))
                with d_col2:
                    if detalhe_desconto > 0: st.metric("Desconto / Acréscimo", f"- {format_currency(detalhe_desconto)}", delta="Desconto", delta_color="normal")
                    elif detalhe_encargos > 0: st.metric("Desconto / Acréscimo", f"+ {format_currency(detalhe_encargos)}", delta="Multa", delta_color="inverse")
                    else: st.metric("Desconto / Acréscimo", "R$ 0,00", delta="Neutro", delta_color="off")
                with d_col3: st.metric("Gastos Variáveis", format_currency(historico_variaveis), delta="Registrados no Mês", delta_color="off")
                with d_col4: st.metric("Total da Fatura" if situacao_selecionada == "Aberta" else "Total Pago", format_currency(total_fatura), delta=f"Situação: {situacao_selecionada}", delta_color="normal" if situacao_selecionada == "Paga" else "off")
                    
                nome_anexo = linha_selecionada.get("nome_anexo", "")
                anexo_url = linha_selecionada.get("anexo", "")
                if pd.notna(nome_anexo) and str(nome_anexo).strip() != "" and pd.notna(anexo_url) and str(anexo_url).strip() != "":
                    st.markdown(f"📎 **Anexo:** [{nome_anexo}]({anexo_url})")
                
                if situacao_selecionada == "Aberta":
                    st.markdown("### 💰 Registrar Pagamento")
                    with st.form(key=f"form_pagamento_{row_id}"):
                        col_pag1, col_pag2 = st.columns([1, 2])
                        with col_pag1: dt_pagamento = st.date_input("Selecione a Data do Pagamento")
                        with col_pag2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            btn_pagar = st.form_submit_button("Confirmar Pagamento", type="primary")
                            
                        if btn_pagar:
                            venc_str = linha_selecionada["vencimento"]
                            venc_date = pd.to_datetime(venc_str).date()
                            dias_atraso_calc = (dt_pagamento - venc_date).days
                            dias_atraso_real = max(0, dias_atraso_calc)
                            status_pag = "Em Atraso" if dias_atraso_real > 0 else "No Prazo"
                            
                            with st.spinner("Atualizando planilha..."):
                                db.update_pagamento(row_id, dt_pagamento, dias_atraso_real, status_pag, "Paga")
                            st.rerun()

                st.markdown("---")
                st.markdown("### ⚙️ Ações da Fatura")
                if st.button("🗑️ Excluir Fatura", type="primary"):
                    with st.spinner("Excluindo da planilha..."):
                        db.delete_fatura(row_id)
                    st.rerun()
                    
                with st.expander("✏️ Editar Dados desta Fatura"):
                    with st.form(key=f"form_edit_{row_id}"):
                        edit_mes = st.text_input("Mês de Referência", value=linha_selecionada['mes_referencia'])
                        venc_atual_str = linha_selecionada["vencimento"]
                        venc_atual_date = pd.to_datetime(venc_atual_str).date()
                        edit_vencimento = st.date_input("Data de Vencimento", value=venc_atual_date)
                        edit_variaveis = st.number_input("Gastos Variáveis", min_value=0.0, value=float(historico_variaveis), format="%.2f", step=10.0)
                        
                        edit_pagamento = None
                        if situacao_selecionada == "Paga":
                            pag_atual_str = linha_selecionada["data_pagamento"]
                            pag_atual_date = pd.to_datetime(pag_atual_str).date() if pd.notna(pag_atual_str) else venc_atual_date
                            edit_pagamento = st.date_input("Data de Pagamento", value=pag_atual_date)
                            
                        btn_salvar = st.form_submit_button("Salvar Alterações")
                        if btn_salvar:
                            with st.spinner("Atualizando fatura..."):
                                if situacao_selecionada == "Paga":
                                    dias_calc = (edit_pagamento - edit_vencimento).days
                                    dias_reais = max(0, dias_calc)
                                    novo_status = "Em Atraso" if dias_reais > 0 else "No Prazo"
                                    db.update_fatura(row_id, edit_mes, edit_vencimento, edit_variaveis, edit_pagamento, novo_status, dias_reais, situacao_selecionada)
                                else:
                                    db.update_fatura(row_id, edit_mes, edit_vencimento, edit_variaveis, None, linha_selecionada["status"], linha_selecionada["dias_atraso"], situacao_selecionada)
                            st.rerun()


# ==========================================
# ABA 2: CONTRATO & CAUÇÃO
# ==========================================
with tab_contrato:
    st.subheader("📝 Dados do Contrato Vigente")
    
    with st.form("form_contrato"):
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            inp_nome = st.text_input("Nome da(o) Inquilina(o)", value=contrato_atual["inquilina"] if contrato_atual else "")
            inp_telefone = st.text_input("Telefone (ID do Cliente)", value=contrato_atual.get("telefone", "") if contrato_atual else "")
            inp_aluguel = st.number_input("Valor Base do Aluguel (R$)", min_value=0.0, value=float(contrato_atual["valor_aluguel"]) if contrato_atual else 1500.0, step=100.0, format="%.2f")
            inp_bonus = st.number_input("Desconto de Pontualidade (R$)", min_value=0.0, value=float(contrato_atual["bonus_pontualidade"]) if contrato_atual else 150.0, step=10.0, format="%.2f")
        with c_col2:
            try:
                default_date = pd.to_datetime(contrato_atual["data_inicio"]).date() if contrato_atual and str(contrato_atual.get("data_inicio")).strip() else date.today()
                if pd.isna(default_date): default_date = date.today()
            except:
                default_date = date.today()
            
            inp_inicio = st.date_input("Data de Início do Contrato", value=default_date)
            inp_caucao = st.number_input("Caução Inicial / Garantia (R$)", min_value=0.0, value=float(contrato_atual["caucao_inicial"]) if contrato_atual else 4500.0, step=100.0, format="%.2f")
            inp_multa = st.number_input("Percentual de Multa ao Dia (%)", min_value=0.0, max_value=100.0, value=float(contrato_atual["percentual_multa"]) if contrato_atual else 0.33, step=0.01, format="%.2f")
            
        btn_salvar_contrato = st.form_submit_button("Salvar Contrato", type="primary")
        
        if btn_salvar_contrato:
            if not inp_nome or not inp_telefone:
                st.error("Por favor, preencha o Nome e o Telefone!")
            else:
                with st.spinner("Salvando as regras do contrato..."):
                    db.save_contrato(inp_nome, inp_aluguel, inp_bonus, inp_multa, inp_caucao, inp_inicio, inp_telefone)
                    if not contrato_atual:
                        db.insert_caucao(inp_inicio, 0.0, inp_caucao)
                st.success("Contrato salvo com sucesso! O sistema foi parametrizado.")
            st.rerun()

    st.markdown("---")
    st.subheader("📈 Atualização Monetária da Caução")
    
    df_caucao = load_caucao()
    ultimo_valor_caucao = 0.0
    
    # Verifica se tem dados e se as colunas existem
    tem_dados_validos = not df_caucao.empty and "valor_atualizado" in df_caucao.columns and len(df_caucao.columns) >= 3
    
    if tem_dados_validos:
        # Filtra linhas vazias acidentais do Google Sheets
        df_valid = df_caucao[df_caucao["valor_atualizado"].astype(str).str.strip() != ""]
        if not df_valid.empty:
            ultimo_valor_caucao = float(df_valid.iloc[-1]["valor_atualizado"])
            
        st.metric("Saldo Atual da Caução", format_currency(ultimo_valor_caucao))
        
        with st.form("form_reajuste_caucao"):
            st.markdown("Aplicar Reajuste (ex: Rendimento da Poupança ou IPCA)")
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                dt_reajuste = st.date_input("Data da Atualização")
            with r_col2:
                perc_reajuste = st.number_input("Índice de Reajuste (%)", value=0.50, step=0.01, format="%.2f")
                
            btn_aplicar = st.form_submit_button("Aplicar Reajuste")
            if btn_aplicar:
                novo_valor_caucao = ultimo_valor_caucao * (1 + (perc_reajuste / 100))
                
                with st.spinner("Registrando reajuste..."):
                    db.insert_caucao(dt_reajuste, perc_reajuste, novo_valor_caucao)
                st.success("Reajuste aplicado com sucesso!")
                st.rerun()
                
        st.markdown("#### Histórico de Rendimentos da Garantia")
        # Mostrar tabela amigável
        df_exibicao_caucao = df_caucao.copy()
        
        # Garante que só vai tentar renomear as 4 colunas esperadas se elas existirem
        if len(df_exibicao_caucao.columns) == 4:
            df_exibicao_caucao.columns = ["ID", "Data da Atualização", "Índice Aplicado (%)", "Valor Atualizado (R$)"]
            st.dataframe(df_exibicao_caucao[["Data da Atualização", "Índice Aplicado (%)", "Valor Atualizado (R$)"]], use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_exibicao_caucao, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma caução registrada no histórico. Salve as configurações do Contrato Vigente para inicializar a garantia.")

# ==========================================
# ABA 3: GESTÃO DE USUÁRIOS
# ==========================================
with tab_usuarios:
    st.subheader("👥 Gestão de Usuários e Acessos")
    df_users = db.get_all_users()
    if not df_users.empty:
        df_exibicao = df_users[["id", "usuario", "role", "telefone_vinculo"]].copy()
        df_exibicao.columns = ["ID", "Usuário", "Perfil", "Telefone (Vínculo)"]
        st.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        
    st.markdown("#### Criar Novo Usuário")
    with st.form("form_novo_usuario"):
        c1, c2 = st.columns(2)
        with c1:
            novo_usu = st.text_input("Nome de Usuário (Login)")
            novo_role = st.selectbox("Perfil", ["Inquilino", "Admin"])
        with c2:
            nova_senha = st.text_input("Senha", type="password")
            novo_tel = st.text_input("Telefone (Usado como ID de vínculo com o Contrato)", help="Deixe em branco para Admin")
        
        if st.form_submit_button("Cadastrar Usuário", type="primary"):
            if not novo_usu or not nova_senha:
                st.error("Usuário e Senha são obrigatórios!")
            else:
                db.insert_user(novo_usu, nova_senha, novo_role, novo_tel)
                st.success("Usuário criado com sucesso!")
                st.rerun()
            
    st.markdown("#### Excluir Usuário")
    with st.form("form_del_usuario"):
        del_id = st.text_input("ID do Usuário a excluir")
        if st.form_submit_button("Excluir Usuário"):
            if del_id.isdigit():
                db.delete_user(del_id)
                st.success("Usuário excluído!")
                st.rerun()
            else:
                st.error("ID inválido.")
