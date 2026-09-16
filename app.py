import streamlit as st
import requests
import pdfplumber
import re

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Ferro+ | Gestão de Inspeções", layout="wide")

# ⚠️ COLOQUE SUA URL AQUI
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbx8hvyk_NTfuhVEBi-LlsXpNr-b2NJNAru_oILk_SlZeLipGjpts1KUuMe7DP-uo5Gvbw/exec"

st.title("🚜 Extrator Inteligente de Inspeções (Ferro+)")
st.markdown("Arraste os PDFs da sua pasta consolidada para extrair todos os dados reais.")

arquivos_pdf = st.file_uploader("Selecione os PDFs das Inspeções", type=['pdf'], accept_multiple_files=True)

if st.button("Processar e Salvar na Planilha", type="primary"):
    
    if not arquivos_pdf:
        st.warning("Selecione pelo menos um arquivo PDF primeiro.")
        st.stop()
        
    for arquivo in arquivos_pdf:
        st.write(f"---")
        st.write(f"📄 **Analisando:** {arquivo.name}")
        
        try:
            with pdfplumber.open(arquivo) as pdf:
                texto_completo = ""
                
                # 1. Lendo as páginas (ignora o resumo final para não duplicar peças)
                for page in pdf.pages:
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        if "Relatório de inspeção resumido" in texto_pagina:
                            texto_completo += texto_pagina.split("Relatório de inspeção resumido")[0]
                            break # Para a leitura ao chegar no resumo
                        texto_completo += texto_pagina + "\n"

                # 2. Extração do Cabeçalho do Equipamento
                os_num = re.search(r'N°\s*(\d+)', texto_completo)
                data_inspecao = re.search(r'Data:\s*([\d/]+)', texto_completo)
                tag_equip = re.search(r'(CS\d+)', texto_completo)
                serie_equip = re.search(r'(KT[A-Z0-9]+)', texto_completo)
                
                # O horímetro geralmente fica no final da linha do cabeçalho
                horimetro_match = re.search(r'SKT110S\s*\n?\s*(\d{3,5})', texto_completo) 
                
                os_val = os_num.group(1) if os_num else "S/N"
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

                # 3. Fatiando os serviços (Backlogs)
                blocos_servico = texto_completo.split("Descrição do serviço")[1:]
                
                for bloco in blocos_servico:
                    # Encontrar Criticidade
                    crit_match = re.search(r'(ALTO|MÉDIO|BAIXO)', bloco, re.IGNORECASE)
                    criticidade = crit_match.group(1).upper() if crit_match else "N/A"
                    
                    # Encontrar Sistema
                    sistema_limpo = bloco.split("Criticidade")[0].replace("SANY Irmen", "").strip()
                    if not sistema_limpo:
                        sistema_limpo = bloco.split("\n")[1].strip()
                        
                    # Encontrar Anotações (Falha)
                    anotacoes = "Sem descrição"
                    if "Anotações" in bloco:
                        anot_parte = bloco.split("Anotações")[1]
                        anot_parte = anot_parte.split("Imagem")[0] # Corta antes da palavra Imagem
                        anotacoes = anot_parte.replace("\n", " ").strip()
                        
                    dados_extracao["backlogs"].append({
                        "sistema": sistema_limpo,
                        "descricao": anotacoes,
                        "criticidade": criticidade
                    })
                    
                    # Encontrar Peças deste serviço
                    if "Relação de peças" in bloco:
                        tabela_str = bloco.split("Relação de peças")[1].split("Anotações")[0]
                        linhas_pecas = tabela_str.strip().split("\n")
                        
                        for linha in linhas_pecas:
                            # Procura um código de peça (geralmente longo e alfanumérico)
                            codigo_match = re.search(r'([A-Z0-9]{8,})', linha)
                            if codigo_match:
                                codigo = codigo_match.group(1)
                                
                                # Tenta isolar a quantidade (um número curto solto)
                                resto_linha = linha.replace(codigo, '').strip()
                                qt_match = re.search(r'\b(\d{1,3})\b', resto_linha)
                                qtd = qt_match.group(1) if qt_match else "1"
                                
                                # O resto é a descrição
                                descricao = resto_linha.replace(qtd, '').strip()
                                descricao = re.sub(r'\d{2}:\d{2}:\d{2}', '', descricao).strip() # Remove hora
                                
                                dados_extracao["pecas"].append({
                                    "codigo": codigo,
                                    "descricao": descricao.strip(' |'),
                                    "qtd": qtd,
                                    "duracao": "N/A"
                                })

                # --- DEBUG VISUAL ---
                with st.expander(f"Ver dados extraídos da OS {os_val}"):
                    st.json(dados_extracao)
                    
                # 4. Envio para a Planilha
                resposta = requests.post(URL_APPS_SCRIPT, json=dados_extracao)
                
                if resposta.status_code == 200 and resposta.json().get('status') == 'sucesso':
                    st.success(f"✅ Dados da OS {os_val} inseridos na Planilha com sucesso!")
                else:
                    st.error(f"❌ Erro ao salvar. Resposta: {resposta.text}")
                    
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
