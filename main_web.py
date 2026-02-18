import flet as ft
import os
import pdfplumber
import re
import numpy as np
import json
from dataclasses import dataclass, field
import os
import asyncio

if "FLET_SECRET_KEY" not in os.environ:
    os.environ["FLET_SECRET_KEY"] = "97eb96726f49b3a6facdbcc1e46d48dd"


@dataclass
class State:
    file_picker: ft.FilePicker | None = None
    picked_files: list[ft.FilePickerFile] = field(default_factory=list)

# Nome do arquivo onde os dados ficarão salvos
MARCADOR_FIM = "Totais: no período"
PADRAO_CODIGO = r"[A-Z]{3,4}\d{2,3}"
PADRAO_SITUACAO = r"\b(AP|RM|RFM|RF)\b"
FILE_PATH = ""


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
            keyboard_type="number", 
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
        async def btn_remover_click(e):
            await on_delete(self)

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
                        on_click=btn_remover_click # Usamos a função async aqui (sem lambda)
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
    state = State()
    file_path = ""
    


    # --- NOVO SISTEMA DE MEMÓRIA (JSON) ---
    async def handle_pick_files(e: ft.Event[ft.Button]):
        state.file_picker = ft.FilePicker()
        files = await state.file_picker.pick_files(allow_multiple=False)
        
        if files:
            # Guarda o arquivo na variável global 'state' para usar depois
            state.picked_files = files
            
            # Atualiza o texto visual e habilita o botão de upload
            selected_files.value = f"Selecionado: {files[0].name}"
            btn_upload.disabled = False
            page.update()

    # -----------------------------------------------------------
    # FUNÇÃO 2: Enviar para o Render e Ler
    # -----------------------------------------------------------
    async def handle_file_upload(e: ft.Event[ft.Button]):
        if not state.picked_files: return
        
        btn_upload.disabled = True
        arquivo = state.picked_files[0]
        
        # Feedback visual para o usuário
        page.show_dialog(ft.SnackBar(ft.Text("Enviando arquivo... Aguarde processamento."), bgcolor="blue"))
        page.update()

        # 1. Faz o Upload
        upload_url = page.get_upload_url(f"{arquivo.name}", 600)
        await state.file_picker.upload(
            files=[
                ft.FilePickerUploadFile(
                    name=arquivo.name,
                    upload_url=upload_url
                )
            ]
        )

        # Caminho onde o arquivo VAI aparecer
        caminho_final = os.path.join("uploads", arquivo.name)
        
        # 2. LOOP DE ESPERA INTELIGENTE (O Segredo)
        # O Render pode levar alguns segundos para 'materializar' o arquivo.
        # Vamos esperar até ele existir e ter tamanho > 0 bytes.
        
        tentativas = 0
        max_tentativas = 15 # Espera no máximo 15 segundos
        arquivo_pronto = False

        while tentativas < max_tentativas:
            if os.path.exists(caminho_final) and os.path.getsize(caminho_final) > 0:
                arquivo_pronto = True
                break # Sai do loop, o arquivo chegou!
            
            # Se não chegou, espera 1 segundo e tenta de novo
            await asyncio.sleep(1)
            tentativas += 1
            print(f"Aguardando arquivo... tentativa {tentativas}")

        # 3. Processamento
        if arquivo_pronto:
            try:
                # Chama a leitura
                leitura_pdf(caminho_final)
                
                # Feedback de Sucesso
                page.show_dialog(ft.SnackBar(ft.Text(f"Processado com sucesso!"), bgcolor="green"))
                
                # Opcional: Apagar do servidor para economizar espaço/segurança
                if os.path.exists(caminho_final):
                    os.remove(caminho_final)
                    
            except Exception as erro:
                page.show_dialog(ft.SnackBar(ft.Text(f"Erro ao ler PDF: {erro}"), bgcolor="red"))
        else:
            page.show_dialog(ft.SnackBar(ft.Text("Erro: O upload demorou muito. Tente novamente."), bgcolor="red"))

        # Reabilita o botão e atualiza
        btn_upload.disabled = False
        page.update()

    # Importante: Certifique-se de ter 'import json' no topo do arquivo

    # 1. Transformamos em ASYNC porque shared_preferences exige await
    async def salvar_tudo():
        # Cria o dicionário de dados (Igual a antes)
        dados = {
            "total_creditos": txt_total_creditos.value,
            "cr_atual": txt_cr_atual.value,
            "periodo_ingresso": txt_periodo.value,
            "lista_disciplinas": []
        }

        for d in disciplinas:
            dados["lista_disciplinas"].append({
                "nome": d.nome.value, 
                "peso": d.peso.value, 
                "nota": d.nota.value
            })
        
        try:
            # CONVERTE O DICIONÁRIO PARA TEXTO (JSON)
            dados_texto = json.dumps(dados)
            
            # SALVA USANDO O NOVO MÉTODO
            await page.shared_preferences.set("dados_cr_v2", dados_texto)
        except Exception as e:
            print(f"Erro ao salvar: {e}")

    # 2. Carregamento também vira ASYNC
    async def carregar_tudo():
        try:
            # Tenta pegar o texto salvo
            # Se não existir, ele retorna None
            dados_texto = await page.shared_preferences.get("dados_cr_v2")
            
            if not dados_texto:
                await adicionar_disciplina()
                return

            # CONVERTE O TEXTO DE VOLTA PARA DICIONÁRIO
            dados = json.loads(dados_texto)

            # Restaura globais
            txt_total_creditos.value = dados.get("total_creditos", "")
            txt_cr_atual.value = dados.get("cr_atual", "")
            txt_periodo.value = dados.get("periodo_ingresso", "")
            
            # Restaura disciplinas
            lista_salva = dados.get("lista_disciplinas", [])
            for item in lista_salva:
                await adicionar_disciplina(dados=item) # Note o await aqui também
            
            if not lista_salva:
                await adicionar_disciplina()

            calcular_cr()
            
        except Exception as ex:
            print(f"Erro ao ler shared_preferences: {ex}")
            await adicionar_disciplina()

    # 3. O evento de mudança precisa ser ASYNC para chamar o salvar_tudo
    async def on_change_geral(e=None):
        calcular_cr()
        await salvar_tudo()

    # 4. Adicionar disciplina precisa ser ASYNC para salvar logo em seguida
    async def adicionar_disciplina(e=None, dados=None):
        n = dados["nome"] if dados else ""
        p = dados["peso"] if dados else ""
        nt = dados["nota"] if dados else ""

        # Passamos on_change_geral (que agora é async)
        d = Disciplina(
            on_delete=remover_disciplina,
            on_change=on_change_geral, 
            n_ini=n, p_ini=p, nt_ini=nt
        )
        disciplinas.append(d)
        lista.controls.append(d.view)
        
        if e is not None: # Se foi clique manual do botão
            await salvar_tudo()
            page.update()

    # 5. Remover também vira async
    async def remover_disciplina(d):
        disciplinas.remove(d)
        lista.controls.remove(d.view)
        await on_change_geral()
        page.update()
    
    
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
                #print(creditos_pdf, notas_pdf)
                
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

    btn_upload = ft.Button(
            content="Upload",
            icon=ft.Icons.UPLOAD,
            on_click=handle_file_upload,
            disabled=True,)

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
        label="Período de ingresso (Ex: 2020/1)",
        keyboard_type="number",
        on_change=on_change_geral
    )
    
    resultado = ft.Text(
        "Aguardando cálculo...",
        size=18,
        weight="bold"
    )
    
    lista = ft.Column(spacing=10)

    page.add(
        ft.Row(controls=[ft.Text("Simulador de CR", size=24, weight="bold"), btn_apoio]),
        txt_total_creditos,
        txt_cr_atual,
        #txt_periodo,
        ft.Row(
            controls=[
                ft.Button(
                    content="Selecionar Boletim",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=handle_pick_files,
                ),
                selected_files := ft.Text(),
            ]
        ),
        btn_upload,
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
    page.run_task(carregar_tudo)

if __name__ == "__main__":
    if not os.path.exists("uploads"):
        os.makedirs("uploads")

    # AQUI MANTEMOS O ft.run COM A CONFIGURAÇÃO DE UPLOAD_DIR
    ft.run(
        main,
        upload_dir="uploads",
        port=int(os.getenv("PORT", 8000))
