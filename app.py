import streamlit as st
import pandas as pd
from datetime import timedelta, date
import io
import calendar
from weasyprint import HTML

# --- FUNÇÕES DE SUPORTE ---

def carregar_dados_web(arquivo_upload):
    """Processa o arquivo vindo do navegador."""
    conteudo = arquivo_upload.read()
    try:
        linhas = conteudo.decode('utf-16-le').splitlines()
    except UnicodeError:
        linhas = conteudo.decode('utf-8').splitlines()
            
    linhas_sem_espaco = [linha.replace(' ', '') for linha in linhas if linha.strip()]
    
    inicio_cabecalho = 0
    for i, linha in enumerate(linhas_sem_espaco):
        if "Date&Time" in linha:
            inicio_cabecalho = i
            break
            
    dados_limpos = linhas_sem_espaco[inicio_cabecalho:]
    df = pd.read_csv(io.StringIO("\n".join(dados_limpos)), sep=';')
    df['Datetime'] = pd.to_datetime(df['Date&Time'], format='%d/%m/%Y%H:%M:%S', errors='coerce')
    return df

def formatar_timedelta(total_segundos):
    """Formata segundos para o padrão +00h00m."""
    horas, resto = divmod(abs(total_segundos), 3600)
    minutos, _ = divmod(resto, 60)
    sinal = "-" if total_segundos < 0 else "+"
    return f"{sinal}{int(horas):02d}h{int(minutos):02d}m"

# --- INTERFACE STREAMLIT ---

st.set_page_config(page_title="Gestor de Frequência", page_icon="🕒", layout="centered")

st.title("🕒 Gestor de Frequência Web")
st.info("Carregue o arquivo CSV para gerar o relatório profissional da Davina.")

# Sidebar de Configuração
st.sidebar.header("Configurações")
arquivo = st.sidebar.file_uploader("Upload do arquivo CSV", type=['csv'])
mes_ref = st.sidebar.text_input("Mês/Ano (MM/AAAA)", value="05/2026")

if arquivo and mes_ref:
    try:
        # 1. Carregamento e Filtro
        df = carregar_dados_web(arquivo)
        mes_num, ano_num = map(int, mes_ref.split('/'))
        
        df_davina = df[df['User'].astype(str).str.lower() == 'davina'].copy()
        df_davina['Mes_Ano'] = df_davina['Datetime'].dt.strftime('%m/%Y')
        df_mes = df_davina[df_davina['Mes_Ano'] == mes_ref].copy()

        if df_mes.empty:
            st.warning("Nenhum dado encontrado para Davina neste período.")
        else:
            df_mes['Data'] = df_mes['Datetime'].dt.date
            
            # 2. Lógica de Cálculo de Horas
            dias_str = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            saldo_total_segundos = 0
            _, num_dias = calendar.monthrange(ano_num, mes_num)
            linhas_tabela_html = ""

            for dia in range(1, num_dias + 1):
                data_atual = date(ano_num, mes_num, dia)
                dia_semana = data_atual.weekday()
                nome_dia = dias_str[dia_semana]
                str_data = data_atual.strftime('%d/%m/%Y')
                
                if dia_semana == 6: # Domingo
                    linhas_tabela_html += f"<tr class='descanso'><td>{str_data}</td><td>{nome_dia}</td><td>---</td><td>---</td><td>Descanso</td><td>---</td><td>---</td></tr>"
                    continue

                registros = df_mes[df_mes['Data'] == data_atual].sort_values('Datetime')

                if len(registros) == 0:
                    linhas_tabela_html += f"<tr class='ausente'><td>{str_data}</td><td>{nome_dia}</td><td>---</td><td>---</td><td>Sem registro</td><td>---</td><td>---</td></tr>"
                    continue

                entrada = registros.iloc[0]['Datetime']
                saida = registros.iloc[-1]['Datetime'] if len(registros) > 1 else None
                str_entrada = entrada.strftime('%H:%M:%S')
                str_saida = saida.strftime('%H:%M:%S') if saida else "---"
                
                if saida is None:
                    linhas_tabela_html += f"<tr class='alerta'><td>{str_data}</td><td>{nome_dia}</td><td>{str_entrada}</td><td>{str_saida}</td><td>Ponto Único</td><td>---</td><td>---</td></tr>"
                else:
                    permanencia = (saida - entrada).total_seconds()
                    esperado = 9 * 3600 if dia_semana < 5 else 4 * 3600
                    saldo_dia = permanencia - esperado
                    saldo_total_segundos += saldo_dia
                    
                    p_str = f"{int(permanencia // 3600):02d}h{int((permanencia % 3600) // 60):02d}m"
                    s_str = formatar_timedelta(saldo_dia)
                    classe = "positivo" if saldo_dia > 0 else "negativo" if saldo_dia < 0 else "zerado"
                    
                    linhas_tabela_html += f"<tr><td>{str_data}</td><td>{nome_dia}</td><td>{str_entrada}</td><td>{str_saida}</td><td>OK</td><td>{p_str}</td><td class='{classe}'>{s_str}</td></tr>"

            # 3. Montagem do HTML Final para o PDF
            saldo_final_str = formatar_timedelta(saldo_total_segundos)
            classe_final = "positivo" if saldo_total_segundos >= 0 else "negativo"

            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial; font-size: 10pt; color: #333; }}
                    .header {{ text-align: center; border-bottom: 2px solid #2c3e50; margin-bottom: 20px; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th {{ background: #2c3e50; color: white; padding: 8px; }}
                    td {{ border: 1px solid #ddd; padding: 6px; text-align: center; }}
                    .descanso {{ background: #f9f9f9; color: #999; }}
                    .ausente {{ color: #e74c3c; }}
                    .positivo {{ color: #27ae60; font-weight: bold; }}
                    .negativo {{ color: #c0392b; font-weight: bold; }}
                    .footer {{ margin-top: 20px; padding: 10px; background: #ecf0f1; text-align: right; font-size: 12pt; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Relatório de Frequência - Davina</h1>
                    <p>Mês de Referência: {mes_ref}</p>
                </div>
                <table>
                    <thead>
                        <tr><th>Data</th><th>Dia</th><th>Entrada</th><th>Saída</th><th>Status</th><th>Permanência</th><th>Saldo</th></tr>
                    </thead>
                    <tbody>{linhas_tabela_html}</tbody>
                </table>
                <div class="footer">
                    <strong>SALDO TOTAL: </strong>
                    <span class="{classe_final}">{saldo_final_str}</span>
                </div>
            </body>
            </html>
            """

            # 4. Botão de Download
            if st.button("✨ Gerar e Visualizar Relatório"):
                pdf_bytes = HTML(string=html_content).write_pdf()
                st.success("PDF gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar PDF Agora",
                    data=pdf_bytes,
                    file_name=f"Relatorio_Davina_{mes_ref.replace('/','_')}.pdf",
                    mime="application/pdf"
                )

    except Exception as e:
        st.error(f"Erro no processamento: {e}")