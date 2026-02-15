# 📊 Simulador de CR (Coeficiente de Rendimento)

> Um aplicativo multiplataforma (Android, Linux, Windows) desenvolvido em Python e Flet para auxiliar estudantes universitários no cálculo e projeção de seu desempenho acadêmico.

![Badge License](https://img.shields.io/github/license/GabrielAmaro/SimuladorCR)
![Badge Python](https://img.shields.io/badge/Python-3.12-blue)
![Badge Flet](https://img.shields.io/badge/Flet-0.21+-purple)

## 🎯 Sobre o Projeto

O **Simulador de CR** permite que o aluno importe seu Boletim Escolar (PDF), extraia automaticamente as notas e créditos, e simule como suas notas futuras impactarão o CR acumulado. O projeto foi otimizado para ler boletins no formato padrão da **UFRJ**, mas permite inserção manual para qualquer universidade.

## ✨ Funcionalidades

- **📄 Leitura Automática de PDF:** Importa boletins e extrai disciplinas, notas e créditos usando `pdfplumber` e Regex.
- **🧮 Cálculo de Previsão:** Simule notas futuras e veja instantaneamente o impacto no seu CR Geral.
- **💾 Salvamento Automático:** Seus dados (disciplinas inseridas, CR atual) são salvos localmente em um arquivo JSON. Você não perde nada ao fechar o app.
- **📱 Multiplataforma:** Roda em Desktop (Windows/Linux/Mac) e Mobile (Android).
- **🚫 Filtros Inteligentes:** Ignora automaticamente trancamentos, isenções e pendências na importação do PDF.

## 🚀 Instalação e Execução Local

Para rodar o código no seu computador, você precisa ter o Python instalado.

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/GabrielAmaro/SimuladorCR.git](https://github.com/GabrielAmaro/SimuladorCR.git)
   cd SimuladorCR
