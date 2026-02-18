import flet as ft
import json
import os
import pdfplumber
import re
import numpy as np
# Nome do arquivo onde os dados ficarão salvos
ARQUIVO_DADOS = "dados_cr.json"
MARCADOR_FIM = "Totais: no período"
PADRAO_CODIGO = r"[A-Z]{3,4}\d{2,3}"
PADRAO_SITUACAO = r"\b(AP|RM|RFM|RF)\b"



def parse_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def parse_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

class Disciplina:
    def __init__(self, on_delete, on_change, n_ini="", p_ini="", nt_ini=""):
        self.nome = ft.TextField(
            label="Disciplina",
            value=n_ini,
            expand=True,
            on_change=on_change
        )

        self.peso = ft.TextField(
            label="Créditos",
            value=p_ini,
            keyboard_type="number", # Usando string para compatibilidade
            on_change=on_change,
            width=110
        )

        self.nota = ft.TextField(
            label="Nota",
            value=nt_ini,
            keyboard_type="number",
            on_change=on_change,
            width=80
        )

        self.view = ft.Container(
            padding=10,
            border=ft.border.all(1, "grey300"),
            border_radius=10,
            content=ft.Column(
                controls=[
                    self.nome,
                    ft.Row(
                        controls=[self.peso, self.nota],
                        spacing=10
                    ),
                    ft.TextButton(
                        "Remover disciplina",
                        style=ft.ButtonStyle(color="red"),
                        on_click=lambda e: on_delete(self)
                    )
                ],
                spacing=10
            )
        )

def main(page: ft.Page):
    page.title = "Simulador de CR"
    page.scroll = "adaptive"
    page.padding = 15
    #page.bgcolor = "grey90" # Corrigido para versão nova

    disciplinas = []
    


    # --- NOVO SISTEMA DE MEMÓRIA (JSON) ---
    async def handle_pick_files(e: ft.Event[ft.Button]):
        files = await ft.FilePicker().pick_files(allow_multiple=True)
        if files:
            leitura_pdf(files[0].path)
            nome_arquivo = files[0].path.split("/")
            page.show_dialog(ft.SnackBar(ft.Text(f"Arquivo aberto: {nome_arquivo[-1]}"), bgcolor="green"))
        else:
            page.update()

    def salvar_tudo():
        # Cria o dicionário de dados
        dados = {
            "total_creditos": txt_total_creditos.value,
            "cr_atual": txt_cr_atual.value,
            "periodo_ingresso": txt_periodo.value,
            "lista_disciplinas": []
        }

        # Preenche a lista de disciplinas
        for d in disciplinas:
            dados["lista_disciplinas"].append({
                "nome": d.nome.value, 
                "peso": d.peso.value, 
                "nota": d.nota.value
            })
        
        # Grava no arquivo JSON (Python Nativo)
        try:
            with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4)
        except Exception as ex:
            print(f"Erro ao salvar: {ex}")

    def carregar_tudo():
        # Verifica se o arquivo existe antes de tentar ler
        if not os.path.exists(ARQUIVO_DADOS):
            adicionar_disciplina() # Começa do zero se não tiver arquivo
            return

        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                dados = json.load(f)

            # Restaura globais
            txt_total_creditos.value = dados.get("total_creditos", "")
            txt_cr_atual.value = dados.get("cr_atual", "")
            txt_periodo.value = dados.get("periodo_ingresso", "")
            
            # Restaura disciplinas
            lista_salva = dados.get("lista_disciplinas", [])
            for item in lista_salva:
                adicionar_disciplina(dados=item)
            
            # Se a lista estava vazia no arquivo, adiciona uma em branco
            if not lista_salva:
                adicionar_disciplina()

            calcular_cr()
            
        except Exception as ex:
            print(f"Erro ao ler arquivo: {ex}")
            adicionar_disciplina()

    # Evento unificado
    def on_change_geral(e=None):
        calcular_cr()
        salvar_tudo()

    txt_total_creditos = ft.TextField(
        label="Créditos Totais Acumulados",
        keyboard_type="number",
        on_change=on_change_geral
    )

    txt_cr_atual = ft.TextField(
        label="CR Acumulado Atual",
        keyboard_type="number",
        on_change=on_change_geral
    )
    
    txt_periodo = ft.TextField(
        label="Período de ingresso na Universisdade (Ex: 2020/1)",
        keyboard_type="number",
        on_change=on_change_geral
    )
    
    resultado = ft.Text(
        "Aguardando cálculo...",
        size=18,
        weight="bold"
    )
    
    alerta = ft.AlertDialog(
        title=ft.Text("Atenção!"),
        content=ft.Text("Preencha o campo com o período de imgresso."),
        actions=[
            ft.TextButton("Entendi", on_click=lambda e: page.pop_dialog())],
        on_dismiss=page.pop_dialog(),

    )

    lista = ft.Column(spacing=10)
    
    
    def leitura_pdf(PATH_BOLETIM):
        try:
            with pdfplumber.open(PATH_BOLETIM) as pdf:
            
                texto_completo = ""
                #MARCADOR_INICIO = txt_periodo.value.replace(".", "/").strip()
                creditos_pdf = []
                notas_pdf = []
                for pagina in pdf.pages:
                    texto_completo += pagina.extract_text() + "\n"

                # ====================================================
                # ETAPA 1: CORTE 
                # ====================================================
                

                FRASE_FIXA = "Sistema de Seleção Unificada em:"
                padrao = fr"{FRASE_FIXA}\s*(\d{{4}}/\d)"
                marc_ini = re.findall(padrao, texto_completo)
                pos_1 = texto_completo.find(marc_ini[0])
                pos_inicio = texto_completo.find(marc_ini[0], pos_1 + 1)

                
                if pos_inicio == -1:
                    pos_inicio = 0 

                # Encontrar o ÚLTIMO "Totais: no período"
                pos_fim = texto_completo.rfind(MARCADOR_FIM)
                
                if pos_fim == -1:
                    pos_fim = len(texto_completo)

                # Corta o texto
    
                texto_util = texto_completo[pos_inicio : pos_fim]
                linhas = texto_util.split('\n')

                # ====================================================
                # ETAPA 2: A BUSCA POR CÓDIGO (ABC123)
                # ====================================================
                
                disciplinas_encontradas = 0	
                for linha in linhas:
                    # Só processa se tiver o código (Ex: MAC123)
                    match_codigo = re.search(PADRAO_CODIGO, linha)
                    if match_codigo:
                        codigo = match_codigo.group()
                        # ====================================================
                        # Esta parte ignora as linhas que possivelmente não 
                        # contribuem para a nota
                        
                        if not re.search(PADRAO_SITUACAO, linha):
                            continue

                        if "*****" in linha:
                            continue

                        linha_teste = linha.replace(codigo, "")
                        linha_teste = re.sub(r"\d{4}[./]\d", "", linha_teste)
                        if not re.search(r"\d", linha_teste):
                            continue
                        # ====================================================

                        # 1. Remove datas (2022/1 ou 2022.1) para não confundir com nota
                        linha_sem_data = re.sub(r"\d{4}[./]\d", "", linha)
                        
                        # 2. Remove o próprio código para ele não ser lido como número
                        linha_limpa = linha_sem_data.replace(codigo, "")

                        # 3. Busca números restantes (Crédito e Nota)
                        numeros = re.findall(r"[\d]+[.,]?\d*", linha_limpa)

                        if len(numeros) >= 2:
                            # Lógica: Penúltimo número = Crédito, Último = Nota
                            nota = numeros[-3]
                            credito = numeros[-5]
                            
                            # 4. Limpa o Nome da Disciplina
                            nome = linha
                            nome = nome.replace(codigo, "")
                            nome = nome.replace(nota, "")
                            nome = nome.replace(credito, "")
                            nome = re.sub(r"\d{4}[./]\d", "", nome) # Tira data do nome
                            nome = nome.replace("-", "").strip()
                            nome = re.sub(r"\d.*", "", nome)
                            nome = nome.replace("-", "").strip()

                            # Filtro de qualidade
                            
                            if len(nome) >= 3:
                                disciplinas_encontradas += 1
                                notas_pdf.append(float(nota))
                                creditos_pdf.append(float(credito))
                print(creditos_pdf, notas_pdf)
                
                txt_total_creditos.value = np.sum(np.array(creditos_pdf))
                txt_cr_atual_calculo = np.sum(np.array(notas_pdf) * np.array(creditos_pdf))/np.sum(np.array(creditos_pdf))
                txt_cr_atual.value  = f"{txt_cr_atual_calculo:.4f}"
                print(txt_total_creditos.value)
                print(txt_cr_atual.value)
                page.update()
        except Exception as e:
            print(f"ERRO: {e}")

    def calcular_cr():
        total_antigo = parse_int(txt_total_creditos.value)
        cr_atual = parse_float(txt_cr_atual.value)

        soma = 0
        pesos = 0

        for d in disciplinas:
            peso = parse_int(d.peso.value)
            nota = parse_float(d.nota.value)

            if peso > 0:
                soma += peso * nota
                pesos += peso

        if total_antigo + pesos > 0:
            novo_cr = (total_antigo * cr_atual + soma) / (total_antigo + pesos)
        else:
            novo_cr = 0

        resultado.value = f"Novo CR Estimado: {novo_cr:.4f}"
        resultado.color = "green" if novo_cr >= cr_atual else "red"

        page.update()

    def adicionar_disciplina(e=None, dados=None):
        n = dados["nome"] if dados else ""
        p = dados["peso"] if dados else ""
        nt = dados["nota"] if dados else ""

        d = Disciplina(
            on_delete=remover_disciplina,
            on_change=on_change_geral,
            n_ini=n, p_ini=p, nt_ini=nt
        )
        disciplinas.append(d)
        lista.controls.append(d.view)
        
        if e is not None: # Se foi clique manual
            salvar_tudo()
            page.update()

    def remover_disciplina(d):
        disciplinas.remove(d)
        lista.controls.remove(d.view)
        on_change_geral()
        page.update()
    # --- APOIO / PIX ---
    
    chave_pix_copia_cola = "00020101021126580014br.gov.bcb.pix01364a063b34-f773-4f81-a183-b0c08e9ae4105204000053039865802BR5920GABRIEL A A DA SILVA6013RIO DE JANEIR62070503***6304A3B1"
    
    def fechar_pix(e):
        page.pop_dialog()
        page.update()

    async def copiar_pix(e):
        await ft.Clipboard().set(chave_pix_copia_cola)
        page.show_dialog(ft.SnackBar(ft.Text("Chave Pix copiada!"), bgcolor="green"))
        page.update()

    dlg_pix = ft.AlertDialog(
        title=ft.Text("Apoie o Projeto"),
        content=ft.Column([
            ft.Text("Este software é gratuito e de código aberto (Open Source). Ele foi desenvolvido para auxiliar alunos a gerenciar melhor seus períodos e continuará sendo livre para sempre. Se este programa economizou seu tempo ou ajudou no seu desenvolvimento academico, considere fazer uma doação voluntária para manter o desenvolvimento ativo e pagar os cafés das madrugadas de programação."),
            ft.Text("Escaneie o QR Code ou copie a chave abaixo:", text_align="center"),
            ft.Container(
                content=ft.Image(
                    src="pix.jpg",
                    width=500, 
                    height=500,
                    fit="contain"
                ),
                alignment=ft.Alignment.CENTER
                
            ),
            ft.TextField(
                value=chave_pix_copia_cola, 
                read_only=True, 
                text_size=12, 
                height=40,
                border_radius=10,
            )
        ], tight=True, width=600, height=650, alignment="center", scroll=ft.ScrollMode.ADAPTIVE),
        actions=[
            ft.TextButton("Fechar", on_click=fechar_pix),
            ft.FilledButton("Copiar Chave", icon=ft.Icons.COPY, on_click=copiar_pix),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def abrir_modal_pix(e):
        page.show_dialog(dlg_pix)
        page.update()

    btn_apoio = ft.FilledButton(
        "Apoiar", 
        icon=ft.Icons.VOLUNTEER_ACTIVISM, 
        style=ft.ButtonStyle(bgcolor=ft.Colors.PINK_400, color=ft.Colors.WHITE),
        on_click=abrir_modal_pix 
    )

    btn_github = ft.Button(
        content="Ver no GitHub",
        icon=ft.Icons.CODE, # Ícone de código, já que o Flet não tem a logo nativa do GitHub
        url="https://github.com/gabrielamaroufrj/SimuladorCR.git" # Substitua pelo seu link real
    )


    page.add(
        ft.Row(controls=[ft.Text("Simulador de CR", size=24, weight="bold"), btn_apoio]),
        txt_total_creditos,
        txt_cr_atual,
        #txt_periodo,
        ft.Row(
            controls=[
                ft.Button(
                    content="Pick files",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=handle_pick_files,
                ),
                selected_files := ft.Text(),
            ]
        ),
        # Nota: FilledButton funciona, mas em versoes novas Button é preferido. 
        # Mantive FilledButton pois funcionou pra você antes.
        ft.FilledButton("Adicionar Disciplina", on_click=adicionar_disciplina),
        ft.Text("Disciplinas:", size=18),  #color="black"),
        lista,
        ft.Container(
            content=resultado,
            padding=12,
            #bgcolor="white",
            border_radius=10,
            border=ft.border.all(1, "grey300")
        ),
        btn_github
    )
    
    # Inicia carregando do JSON
    carregar_tudo()
    page.update()

if __name__ == "__main__":
    ft.run(main)
