import streamlit as st
import requests
import base64
import pdfplumber
import io
import re

st.set_page_config(page_title="Ferro+ | Gestão de Inspeções", layout="wide")

# ⚠️ COLOQUE SUA URL AQUI NOVAMENTE
URL_APPS_SCRIPT = "COLE_AQUI_A_SUA_URL_DO_APPS_SCRIPT"

st.title("🚜 Extrator de Inspeções e Backlogs (Ferro+)")
st.markdown("Busca automática de PDFs no Google Drive, extração de peças e envio para Planilha.")

if st.button("Buscar e Processar PDFs do Drive", type="primary"):
    with st.spinner("Conectando ao Google Drive e buscando PDFs..."):
        try:
            resposta = requests.get(URL_APPS_SCRIPT)
            
            # --- MODO DE DIAGNÓSTICO ---
            if resposta.status_code != 200:
                st.error(f"Erro de Conexão. O Google retornou o código HTTP {resposta.status_code}")
                st.stop()
                
            texto_retorno = resposta.text
            
            # Verifica se o Google retornou uma tela de erro/login HTML em vez dos nossos dados
            if "<html" in texto_retorno.lower() or "<!doctype html>" in texto_retorno.lower():
                st.error("🚨 O Google bloqueou o acesso e retornou uma página da web (provavelmente pedindo login).")
                st.warning("Verifique se 'Quem tem acesso' está como 'Qualquer pessoa' no Apps Script e se você publicou uma 'Nova Versão'.")
                with st.expander("Ver o que o Google respondeu escondido:"):
                    st.code(texto_retorno[:1000]) # Mostra o motivo real do bloqueio
                st.stop()

            # Tenta converter os dados
            try:
                pdfs_encontrados = resposta.json()
            except Exception as json_err:
                st.error("🚨 O Google não enviou os dados no formato correto (JSON).")
                with st.expander("Ver o que o Google respondeu escondido:"):
                    st.code(texto_retorno[:1000])
                st.stop()
            # --------------------------------

            # Trata se o Google enviou apenas uma mensagem de erro em formato válido
            if isinstance(pdfs_encontrados, dict) and "erro" in pdfs_encontrados:
                st.error(f"⚠️ O Script encontrou um erro no Drive: {pdfs_encontrados['erro']}")
                st.stop()
            elif isinstance(pdfs_encontrados, dict):
                pdfs_encontrados = [pdfs_encontrados]
                
            if not pdfs_encontrados or len(pdfs_encontrados) == 0:
                st.warning("Nenhum PDF encontrado nas pastas.")
                st.stop()
                
            # Processamento real
            for pdf_data in pdfs_encontrados:
                if not isinstance(pdf_data, dict) or 'base64' not in pdf_data:
                    continue 
                    
                st.write(f"📄 **Lendo arquivo:** {pdf_data['nome']}")
                
                pdf_bytes = base64.b64decode(pdf_data['base64'])
                arquivo_memoria = io.BytesIO(pdf_bytes)
                
                with pdfplumber.open(arquivo_memoria) as pdf:
                    texto_completo = ""
                    for pagina in pdf.pages:
                        texto_completo += pagina.extract_text() + "\n"
                        
                    match_os = re.search(r'N°\s*(\d+)', texto_completo)
                    match_data = re.search(r'Data:\s*([\d/]+)', texto_completo)
                    match_tag = re.search(r'(CS\d+)', texto_completo)
                    
                    os_num = match_os.group(1) if match_os else "00000"
                    data_inspecao = match_data.group(1) if match_data else "S/D"
                    tag_equip = match_tag.group(1) if match_tag else "S/T"
                    
                    dados_extraidos = {
                        "os": os_num,
                        "data": data_inspecao,
                        "tag": tag_equip,
                        "serie": "KT105...",
                        "marca": "SANY", 
                        "modelo": "SKT110S",
                        "horimetro": "7033", 
                        "backlogs": [{"sistema": "TESTE SUCESSO", "descricao": "Leitura ok", "criticidade": "MÉDIO"}],
                        "pecas": [{"codigo": "123", "descricao": "PEÇA", "qtd": 1, "duracao": "00:00:00"}]
                    }
                    
                    resposta_post = requests.post(URL_APPS_SCRIPT, json=dados_extraidos)
                    
                    if resposta_post.json().get('status') == 'sucesso':
                        st.success(f"✅ Dados da OS {os_num} ({tag_equip}) salvos na Planilha!")
                    else:
                        st.error(f"❌ Erro ao salvar na planilha: {resposta_post.text}")
                        
        except Exception as e:
            st.error(f"Erro Diagnóstico: {e}")
