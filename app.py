import streamlit as st
import requests
import pdfplumber
import re

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Ferro+ | Gestão de Inspeções", layout="wide")

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbx8hvyk_NTfuhVEBi-L1sXpNr-b2NJNAru_oiLk_S1ZeLipGjpts1KUuMe7DP-uo5Gvbw/exec"

st.title("🚜 Extrator Inteligente de Inspeções (Ferro+)")
st.markdown("Arraste os PDFs da sua pasta consolidada para extrair os dados para a Planilha.")

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
                
                # 1. Leitura das páginas (ignora o resumo final)
                for page in pdf.pages:
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        if "Relatório de inspeção resumido" in texto_pagina:
                            texto_completo += texto_pagina.split("Relatório de inspeção resumido")[0]
                            break
                        texto_completo += texto_pagina + "\n"

                # 2. Extração do Cabeçalho
                match_os = re.search(r'(?:N[°º]|O\.?S\.?|Ordem\s*de\s*Serviço)\s*:?\s*(\d+)', texto_completo, re.IGNORECASE)
                if not match_os:
                    match_os = re.search(r'OS_?(\d+)', arquivo.name, re.IGNORECASE)

                data_inspecao = re.search(r'Data:\s*([\d/]+)', texto_completo)
                
                tag_equip = re.search(r'(CS\d+)', texto_completo)
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
                    # Captura Criticidade
                    crit_match = re.search(r'(ALTO|MÉDIO|BAIXO|MODERADO|CRÍTICO|IMPORTANTE)', bloco, re.IGNORECASE)
                    criticidade = crit_match.group(1).upper() if crit_match else "MODERADO"
                    
                    # Captura Nome do Sistema / Item Inspecionado
                    # Pega as primeiras linhas do bloco ignorando cabeçalhos conhecidos
                    linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
                    sistema_limpo = "SISTEMA DIVERSO"
                    
                    for linha in linhas:
                        # Descarta linhas com rótulos genéricos
                        if any(rotulo in linha.lower() for rotulo in ["criticidade", "sany irmen", "descrição do serviço", "relação de peças", "anotações"]):
                            continue
                        if len(linha) > 3: # Primeira linha útil é o sistema/item
                            sistema_limpo = linha
                            break
                        
                    # Captura Anotações / Descrição detalhada da falha
                    anotacoes = "Sem descrição complementar"
                    if "Anotações" in bloco:
                        anot_parte = bloco.split("Anotações")[1]
                        anot_parte = anot_parte.split("Imagem")[0].split("Relação de peças")[0]
                        anot_texto = anot_parte.replace("\n", " ").strip()
                        if len(anot_texto) > 2:
                            anotacoes = anot_texto
                            
                    dados_extracao["backlogs"].append({
                        "sistema": sistema_limpo,
                        "descricao": anotacoes,
                        "criticidade": criticidade
                    })
                    
                    # Captura Tabela de Peças
                    if "Relação de peças" in bloco:
                        trecho_pecas = bloco.split("Relação de peças")[1]
                        # Limita a leitura até a próxima seção
                        for marcador in ["Anotações", "Imagem", "Descrição do serviço"]:
                            if marcador in trecho_pecas:
                                trecho_pecas = trecho_pecas.split(marcador)[0]
                                
                        linhas_pecas = trecho_pecas.strip().split("\n")
                        
                        for linha in linhas_pecas:
                            # Filtra linhas com códigos alfanuméricos de peças (ex: 60123456 ou B2299...)
                            codigo_match = re.search(r'([A-Z0-9]{6,15})', linha)
                            if codigo_match:
                                codigo = codigo_match.group(1)
                                resto_linha = linha.replace(codigo, '').strip()
                                
                                # Procura quantidade
                                qt_match = re.search(r'\b(\d{1,3})\b', resto_linha)
                                qtd = qt_match.group(1) if qt_match else "1"
                                
                                # O resto é a descrição do nome da peça
                                desc_peca = resto_linha.replace(qtd, '').strip()
                                desc_peca = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc_peca).strip(' |:-')
                                
                                if len(desc_peca) > 2 and desc_peca.lower() not in ["código", "descrição", "qtd"]:
                                    dados_extracao["pecas"].append({
                                        "codigo": codigo,
                                        "descricao": desc_peca,
                                        "qtd": qtd,
                                        "duracao": "N/A"
                                    })

                # Exibe resumo visual no Streamlit antes de enviar
                with st.expander(f"🔍 Ver dados extraídos da OS {os_val} ({tag_val})"):
                    st.json(dados_extracao)
                    
                # 4. Envio para o Google Apps Script
                resposta = requests.post(URL_APPS_SCRIPT, json=dados_extracao)
                
                if resposta.status_code == 200 and resposta.json().get('status') == 'sucesso':
                    st.success(f"✅ OS {os_val} ({tag_val}) gravada com sucesso!")
                else:
                    st.error(f"❌ Erro ao salvar OS {os_val}: {resposta.text}")
                    
        except Exception as e:
            st.error(f"Erro ao processar o arquivo {arquivo.name}: {e}")
