import streamlit as st
import pandas as pd
from datetime import timedelta, date
import io
import calendar
from weasyprint import HTML

# --- 1. FUNÇÕES DE SUPORTE (Lógica de Dados) ---

def carregar_dados_web(arquivo_upload):
    """Lê o arquivo CSV tratando codificação e cabeçalhos."""
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
    """Formata segundos para o padrão de horas e minutos (+00h00m)."""
    horas, resto = divmod(abs(total_segundos), 3600)
    minutos, _ = divmod(resto, 60)
    sinal = "-" if total_segundos < 0 else "+"
    return f"{sinal}{int(horas):02d}h{int(minutos):02d}m"

# --- 2. INTERFACE STREAMLIT ---

st.set_page_config(page_title="Gestor de Frequência", page_icon="🕒")

st.title("🕒 Relatório de Frequência Web")
st.markdown("Gere relatórios profissionais em PDF de forma simples.")

# Configurações na barra lateral
st.sidebar.header("Parâmetros")
arquivo = st.sidebar.file_uploader("Selecione o arquivo CSV", type=['csv'])
mes_ref = st.sidebar.text_input("Mês/Ano (MM/AAAA)", value="05/2026")

if arquivo and mes_ref:
    try:
        # Processamento inicial
        df_completo = carregar_dados_web(arquivo)
        mes_num, ano_num = map(int, mes_ref.split('/'))
        
        # Filtro específico para a funcionária
        df_davina = df_completo[df_completo['User'].astype(str).str.lower() == 'davina'].copy()
        df_davina['Mes_Ano'] = df_davina['Datetime'].dt.strftime('%m/%Y')
        df_mes = df_davina[df_davina['Mes_Ano'] == mes_ref].copy()

        if df_mes.empty:
            st.warning(f"Nenhum registro para Davina em {mes_ref}.")
        else:
            df_mes['Data'] = df_mes['Datetime'].dt.date
            dias_str = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            saldo_total_segundos = 0
            _, num_dias = calendar.monthrange(ano_num, mes_num)
            linhas_html = ""

            # Loop de construção da tabela dia a dia
            for dia in range(1, num_dias + 1):
                data_atual = date(ano_num, mes_num, dia)
                dia_semana = data_atual.weekday()
                str_data = data_atual.strftime('%d/%m/%Y')
                nome_dia = dias_str[dia_semana]
                
                # Regra de Domingo
                if dia_semana == 6:
                    linhas_html += f"<tr class='descanso'><td>{str_data}</td><td>{nome_dia}</td><td>---</td><td>---</td><td>Descanso</td><td>---</td><td>---</td></tr>"
                    continue

                registros = df_mes[df_mes['Data'] == data_atual].sort_values('Datetime')

                if len(registros) == 0:
                    linhas_html += f"<tr class='ausente'><td>{str_data}</td><td>{nome_dia}</td><td>---</td><td>---</td><td>Sem registro</td><td>---</td><td>---</td></tr>"
                    continue

                entrada = registros.iloc[0]['Datetime']
                saida = registros.iloc[-1]['Datetime'] if len(registros) > 1 else None
                
                if not saida:
                    linhas_html += f"<tr class='alerta'><td>{str_data}</td><td>{nome_dia}</td><td>{entrada.strftime('%H:%M:%S')}</td><td>---</td><td>Ponto Único</td><td>---</td><td>---</td></tr>"
                else:
                    permanencia = (saida - entrada).total_seconds()
                    esperado = 9 * 3600 if dia_semana < 5 else 4 * 3600
                    saldo_dia = permanencia - esperado
                    saldo_total_segundos += saldo_dia
                    
                    classe = "positivo" if saldo_dia > 0 else "negativo" if saldo_dia < 0 else ""
                    linhas_html += f"<tr><td>{str_data}</td><td>{nome_dia}</td><td>{entrada.strftime('%H:%M:%S')}</td><td>{saida.strftime('%H:%M:%S')}</td><td>OK</td><td>{int(permanencia//3600):02d}h{int((permanencia%3600)//60):02d}m</td><td class='{classe}'>{formatar_timedelta(saldo_dia)}</td></tr>"

            # Definição do conteúdo HTML para o PDF
            saldo_final_str = formatar_timedelta(saldo_total_segundos)
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    @page {{ size: A4; margin: 8mm; }}
                    body {{ font-family: 'Segoe UI', Arial; color: #2c3e50; font-size: 8.5pt; line-height: 1.2; }}
                    .header {{ text-align: center; border-bottom: 2px solid #34495e; padding-bottom: 5px; margin-bottom: 10px; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th {{ background: #34495e; color: white; padding: 5px; font-size: 8pt; }}
                    td {{ border-bottom: 1px solid #eee; padding: 4px; text-align: center; }}
                    .descanso {{ color: #bdc3c7; font-style: italic; }}
                    .ausente {{ color: #e74c3c; }}
                    .positivo {{ color: #27ae60; font-weight: bold; }}
                    .negativo {{ color: #c0392b; font-weight: bold; }}
                    .footer {{ margin-top: 10px; padding: 8px; background: #34495e; color: white; text-align: right; border-radius: 4px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2 style="margin:0;">Relatório de Frequência</h2>
                    <p style="margin:2px;">Funcionária: <strong>DAVINA</strong> | Período: {mes_ref}</p>
                </div>
                <table>
                    <thead>
                        <tr><th>Data</th><th>Dia</th><th>Entrada</th><th>Saída</th><th>Status</th><th>Carga</th><th>Saldo</th></tr>
                    </thead>
                    <tbody>{linhas_html}</tbody>
                </table>
                <div class="footer">
                    <strong>SALDO TOTAL NO MÊS: {saldo_final_str}</strong>
                </div>
            </body>
            </html>
            """

            if st.button("🚀 Gerar Relatório PDF"):
                pdf_bytes = HTML(string=html_content).write_pdf()
                st.success("PDF gerado com sucesso!")
                st.download_button("📥 Baixar PDF", data=pdf_bytes, file_name=f"Relatorio_Davina_{mes_ref.replace('/','_')}.pdf")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
