import streamlit as st
import requests
import pdfplumber
import re

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Ferro+ | Gestão de Inspeções", layout="wide")

# ⚠️ COLOQUE AQUI A SUA URL DO GOOGLE APPS SCRIPT (WEB APP)
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbx8hvyk_NTfuhVEBi-LlsXpNr-b2NJNAru_oILk_SlZeLipGjpts1KUuMe7DP-uo5Gvbw/exec"

st.title("🚜 Extrator Inteligente de Inspeções (Ferro+)")
st.markdown("Arraste os PDFs da sua pasta consolidada para extrair todos os dados reais e enviar para a Planilha.")

# Componente de Upload de arquivos
arquivos_pdf = st.file_uploader(
    "Selecione os PDFs das Inspeções", 
    type=['pdf'], 
    accept_multiple_files=True
)

if st.button("Processar e Salvar na Planilha", type="primary"):
    
    if not arquivos_pdf:
        st.warning("Selecione pelo menos um arquivo PDF primeiro.")
        st.stop()
        
    for arquivo in arquivos_pdf:
        st.write("---")
        st.write(f"📄 **Analisando:** {arquivo.name}")
        
        try:
            with pdfplumber.open(arquivo) as pdf:
                texto_completo = ""
                
                # 1. Leitura das páginas (ignora o resumo final para não duplicar dados)
                for page in pdf.pages:
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        if "Relatório de inspeção resumido" in texto_pagina:
                            texto_completo += texto_pagina.split("Relatório de inspeção resumido")[0]
                            break
                        texto_completo += texto_pagina + "\n"

                # 2. Extração do Cabeçalho do Equipamento (Regex Flexível)
                # Tenta buscar no texto do PDF
                match_os = re.search(r'(?:N[°º]|O\.?S\.?|Ordem\s*de\s*Serviço)\s*:?\s*(\d+)', texto_completo, re.IGNORECASE)
                
                # Se não encontrar no texto do PDF, pega o número da OS direto do nome do arquivo (ex: OS_9515...)
                if not match_os:
                    match_os = re.search(r'OS_?(\d+)', arquivo.name, re.IGNORECASE)

                data_inspecao = re.search(r'Data:\s*([\d/]+)', texto_completo)
                
                tag_equip = re.search(r'(CS\d+)', texto_completo)
                # Se não achar a TAG no texto, busca no nome do arquivo (ex: equip_CS26)
                if not tag_equip:
                    tag_equip = re.search(r'(CS\d+)', arquivo.name, re.IGNORECASE)

                serie_equip = re.search(r'(KT[A-Z0-9]+)', texto_completo)
                horimetro_match = re.search(r'SKT110S\s*\n?\s*(\d{3,5})', texto_completo) 
                
                os_val = match_os.group(1) if match_os else "S/N"
                tag_val = tag_equip.group(1) if tag_equip else "S/T"
                
                dados_extracao = {
                    "os": os_val,
                    "data": data_inspecao.group(1) if data_inspecao else "S/D",
                    "tag": tag_val,
                    "serie": serie_equip.group(1) if serie_equip else "S/S",
                    "marca": "SANY",
                    "modelo": "SKT110S",
                    "horimetro": horimetro_match.group(1) if horimetro_match else "0",
                    "backlogs": [],
                    "pecas": []
                }

                # 3. Fatiamento dos serviços/sistemas (Backlogs)
                blocos_servico = texto_completo.split("Descrição do serviço")[1:]
                
                for bloco in blocos_servico:
                    # Busca Criticidade
                    crit_match = re.search(r'(ALTO|MÉDIO|BAIXO|MODERADO|CRÍTICO|IMPORTANTE)', bloco, re.IGNORECASE)
                    criticidade = crit_match.group(1).upper() if crit_match else "N/A"
                    
                    # Busca Sistema
                    sistema_limpo = bloco.split("Criticidade")[0].replace("SANY Irmen", "").strip()
                    if not sistema_limpo:
                        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
                        sistema_limpo = linhas[0] if linhas else "SISTEMA DIVERSO"
                        
                    # Busca Anotações (Descrição da Falha)
                    anotacoes = "Sem descrição"
                    if "Anotações" in bloco:
                        anot_parte = bloco.split("Anotações")[1]
                        anot_parte = anot_parte.split("Imagem")[0] # Descarta trechos de imagem
                        anotacoes = anot_parte.replace("\n", " ").strip()
                        
                    dados_extracao["backlogs"].append({
                        "sistema": sistema_limpo,
                        "descricao": anotacoes,
                        "criticidade": criticidade
                    })
                    
                    # Busca Relação de Peças
                    if "Relação de peças" in bloco:
                        tabela_str = bloco.split("Relação de peças")[1].split("Anotações")[0]
                        linhas_pecas = tabela_str.strip().split("\n")
                        
                        for linha in linhas_pecas:
                            codigo_match = re.search(r'([A-Z0-9]{8,})', linha)
                            if codigo_match:
                                codigo = codigo_match.group(1)
                                resto_linha = linha.replace(codigo, '').strip()
                                qt_match = re.search(r'\b(\d{1,3})\b', resto_linha)
                                qtd = qt_match.group(1) if qt_match else "1"
                                
                                descricao = resto_linha.replace(qtd, '').strip()
                                descricao = re.sub(r'\d{2}:\d{2}:\d{2}', '', descricao).strip() # Limpa horários
                                
                                dados_extracao["pecas"].append({
                                    "codigo": codigo,
                                    "descricao": descricao.strip(' |'),
                                    "qtd": qtd,
                                    "duracao": "N/A"
                                })

                # Exibe um menu expansível com o resumo para conferência visual
                with st.expander(f"🔍 Ver dados extraídos da OS {os_val} ({tag_val})"):
                    st.json(dados_extracao)
                    
                # 4. Envio dos dados estruturados para o Google Apps Script
                resposta = requests.post(URL_APPS_SCRIPT, json=dados_extracao)
                
                if resposta.status_code == 200 and resposta.json().get('status') == 'sucesso':
                    st.success(f"✅ Dados da OS {os_val} ({tag_val}) inseridos na Planilha com sucesso!")
                else:
                    st.error(f"❌ Erro ao salvar OS {os_val}. Resposta: {resposta.text}")
                    
        except Exception as e:
            st.error(f"Erro ao processar o arquivo {arquivo.name}: {e}")
