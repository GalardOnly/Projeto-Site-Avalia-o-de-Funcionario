#  Projeto: Avaliação de Funcionário (Controle de Ponto)

Este projeto é uma aplicação web interativa desenvolvida para automatizar a análise de folhas de ponto e controle de jornada de trabalho.

Através do upload de arquivos de registro (formato `.txt`), o sistema processa os dados, aplica regras de negócios (horários esperados, tolerâncias) e gera relatórios detalhados sobre horas extras, atrasos e ausências.

##  Funcionalidades

* **Processamento de Arquivos:** Leitura e tratamento de arquivos de ponto brutos (Tab-separated values).
* **Cálculo Automático de Jornada:**
    * Identificação de batidas (Entrada, Saída Almoço, Volta Almoço, Saída Casa).
    * Comparação com horário padrão (07:30 às 17:50).
    * Cálculo de penalidades (Atrasos na entrada, saídas antecipadas, almoço excedido).
* **Regras de Fim de Semana:** Lógica diferenciada para sábados e domingos (cálculo de hora extra integral ou jornada direta).
* **Dashboard Interativo:**
    * Métricas visuais de Horas Faltantes vs. Horas Extras.
    * Detecção automática de dias de ausência (Faltas).
* **Relatórios Exportáveis:** Download das tabelas processadas e resumos individuais em formato CSV.

##  Tecnologias Utilizadas

* **Linguagem:** Python
* **Interface Web:** [Streamlit](https://streamlit.io/)
* **Manipulação de Dados:** Pandas & NumPy

## 📂 Estrutura do Projeto

* `app.py`: Código principal da aplicação contendo a lógica de processamento (`processar_folha_ponto`) e a interface Streamlit.
* `Requeriments.txt`: Lista de dependências do projeto.

##  Como Executar o Projeto

Siga os passos abaixo para rodar a aplicação na sua máquina local:

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/GalardOnly/Projeto-Site-Avalia-o-de-Funcionario.git](https://github.com/GalardOnly/Projeto-Site-Avalia-o-de-Funcionario.git)
    cd Projeto-Site-Avalia-o-de-Funcionario
    ```

2.  **Crie um ambiente virtual (Recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    *Nota: O arquivo no repositório está nomeado como `Requeriments.txt`*
    ```bash
    pip install -r Requeriments.txt
    ```

4.  **Execute o Dashboard:**
    ```bash
    streamlit run app.py
    ```

5.  **Acesse no navegador:**
    O terminal irá mostrar um link local, geralmente: `http://localhost:8501`

##  Regras de Negócio Implementadas

O algoritmo considera os seguintes horários para cálculo de penalidades e extras:
* **Entrada:** 07:30
* **Saída Almoço:** 11:30
* **Volta Almoço:** 13:00 (Duração esperada: 1h30m / Tolerância aplicada no código: 89 min)
* **Saída:** 17:50

##  Autores

* **GalardOnly** - *Desenvolvimento Full Stack*

---
*Projeto desenvolvido para fins acadêmicos e de portfólio.*
