
# Acessórias — Diagnóstico por Cliente (Streamlit)

Projeto completo para diagnosticar **Entregas, Solicitações, Obrigações, Processos e Responsáveis** do Acessórias,
com **Página de Resumo**, **Relatórios (ajuste de métricas e filtros)** e **exportação em Markdown**.

## 🧩 Estrutura
- `app.py` — App principal (abas: Resumo, Entregas, Solicitações, Obrigações, Processos, Responsáveis, Relatórios, Exportações)
- `extras/` — versões alternativas:
  - `app_unificado.py` — ingestão com mapeadores e visões principais
  - `app_unificado_resumo.py` — com Página de Resumo
- `.streamlit/config.toml` — tema e config do Streamlit
- `requirements.txt` — dependências
- `templates/` — arquivos-modelo (CSV) para facilitar mapeamento
- `samples/` — dados de exemplo (fictícios) para testes

## ▶️ Como rodar
```bash
pip install -r requirements.txt
streamlit run app.py
```
O app abre no browser (porta padrão 8501).

## 📂 Uploads esperados (por aba)
- **Entregas (CSV)** — gestão de entregas exportada do Acessórias
- **Solicitações (XLSX/CSV)**
- **Obrigações (XLSX/CSV)**
- **Processos (XLSX/CSV)**
- **Responsáveis (XLS/XLSX/CSV)**

> As colunas mudam por cliente. Use o **Mapeador de Colunas** em cada aba para alinhar os nomes.

## 🧠 Página de Resumo
- KPIs gerais (Entregas, Solicitações, Processos)
- **Dados perigosos**: entregas em risco (≤ X dias), pendentes vencidas, solicitações abertas ≥ Y dias, prioridade alta sem atualização ≥ Z dias, processos ≥ W dias em andamento
- Ranking de empresas com mais atrasos (últimos N dias)

## 📝 Relatórios (Ajuste de Métricas)
- Ajuste de limites: X/Y/Z/W/N dias
- Filtros globais: empresas, departamentos, responsáveis
- Gera **Resumo Analítico** em Markdown com números e rankings
- Botão para **download** (`relatorio_resumo.md`)

## 📑 Modelos de planilha (templates)
Veja em `templates/` os CSVs com cabeçalhos sugeridos para mapeamento:

- `template_entregas.csv`
- `template_solicitacoes.csv`
- `template_obrigacoes.csv`
- `template_processos.csv`
- `template_responsaveis.csv`

Você pode abrir esses arquivos e conferir como mapear cada coluna no app.

## 💡 Dicas
- Para `.xls` antigos, instale `xlrd` (já incluso em `requirements.txt`).
- Datas: o app tenta converter automaticamente (dia/mês/ano). Ajuste o mapeamento quando necessário.
- Exporte datasets tratados nas abas **Exportações** e use no seu diagnóstico final.

---

Feito para **mudar de cliente a cada diagnóstico** — basta fazer upload, mapear e gerar o resumo.
