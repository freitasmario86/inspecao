import streamlit as st
import requests
import base64
import pdfplumber
import io
import re
import pandas as pd

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Ferro+ | Gestão de Inspeções", layout="wide")

# ⚠️ COLOQUE AQUI A URL DO SEU GOOGLE APPS SCRIPT (WEB APP)
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbx8hvyk_NTfuhVEBi-LlsXpNr-b2NJNAru_oILk_SlZeLipGjpts1KUuMe7DP-uo5Gvbw/exec"

st.title("🚜 Extrator de Inspeções e Backlogs (Ferro+)")
st.markdown("Busca automática de PDFs no Google Drive, extração de peças e envio para Planilha.")

if st.button("Buscar e Processar PDFs do Drive", type="primary"):
    
    if URL_APPS_SCRIPT == "https://script.google.com/macros/s/AKfycbx8hvyk_NTfuhVEBi-LlsXpNr-b2NJNAru_oILk_SlZeLipGjpts1KUuMe7DP-uo5Gvbw/exec":
        st.error("⚠️ Você esqueceu de colocar a URL do Apps Script no código!")
        st.stop()
        
    with st.spinner("Conectando ao Google Drive e buscando PDFs..."):
        try:
            # 1. Solicita os PDFs para o Apps Script
            resposta = requests.get(URL_APPS_SCRIPT)
            
            if resposta.status_code != 200:
                st.error("Erro ao conectar com o Google Drive.")
                st.stop()
                
            pdfs_encontrados = resposta.json()
            
            if not pdfs_encontrados or len(pdfs_encontrados) == 0:
                st.warning("Nenhum PDF encontrado nas pastas.")
                st.stop()
                
            # 2. Processa cada PDF recebido
            for pdf_data in pdfs_encontrados:
                if 'erro' in pdf_data:
                    st.error(f"Erro no Apps Script: {pdf_data['erro']}")
                    continue
                    
                st.write(f"📄 **Lendo arquivo:** {pdf_data['nome']}")
                
                # Descompacta o Base64 para transformar em arquivo de memória (PDF)
                pdf_bytes = base64.b64decode(pdf_data['base64'])
                arquivo_memoria = io.BytesIO(pdf_bytes)
                
                # 3. Extração usando pdfplumber
                with pdfplumber.open(arquivo_memoria) as pdf:
                    texto_completo = ""
                    for pagina in pdf.pages:
                        texto_completo += pagina.extract_text() + "\n"
                        
                    # --- LÓGICA DE EXTRAÇÃO (REGEX) ---
                    # Busca Número da OS e Data
                    match_os = re.search(r'N°\s*(\d+)', texto_completo)
                    match_data = re.search(r'Data:\s*([\d/]+)', texto_completo)
                    
                    # Busca Equipamento (Tag, Série, Horímetro)
                    match_tag = re.search(r'(CS\d+)', texto_completo)
                    match_serie = re.search(r'(KT\w+)', texto_completo)
                    match_horimetro = re.search(r'(\d+)\nDescrição', texto_completo) # Ajuste dependendo do layout
                    
                    os_num = match_os.group(1) if match_os else "00000"
                    data_inspecao = match_data.group(1) if match_data else "S/D"
                    tag_equip = match_tag.group(1) if match_tag else "S/T"
                    serie_equip = match_serie.group(1) if match_serie else "S/S"
                    
                    # Montando o pacote de dados para enviar de volta à Planilha
                    # Nota: Para simplificar, estamos enviando exemplos estruturados baseados no seu documento. 
                    # Uma extração completa de tabelas pode exigir `pdf.extract_tables()`.
                    dados_extraidos = {
                        "os": os_num,
                        "data": data_inspecao,
                        "tag": tag_equip,
                        "serie": serie_equip,
                        "marca": "SANY", 
                        "modelo": "SKT110S",
                        "horimetro": "7033", 
                        "backlogs": [
                            {"sistema": "SISTEMA EXTRAÍDO", "descricao": "Leitura automática via PDF", "criticidade": "MÉDIO"}
                        ],
                        "pecas": [
                            {"codigo": "EXTRAIDO-01", "descricao": "PEÇA IDENTIFICADA NO PDF", "qtd": 1, "duracao": "00:00:00"}
                        ]
                    }
                    
                    # 4. Envia os dados para a Planilha via Apps Script (POST)
                    resposta_post = requests.post(URL_APPS_SCRIPT, json=dados_extraidos)
                    
                    if resposta_post.json().get('status') == 'sucesso':
                        st.success(f"✅ Dados da OS {os_num} ({tag_equip}) salvos na Planilha!")
                    else:
                        st.error(f"❌ Erro ao salvar dados de {pdf_data['nome']}: {resposta_post.text}")
                        
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado: {e}")

st.divider()
st.subheader("💡 Próximos Passos (Dashboard)")
st.info("Assim que os dados começarem a preencher a sua Planilha do Google, usaremos o Looker Studio ou atualizaremos este app para mostrar os gráficos e a matriz de status dos Backlogs.")
