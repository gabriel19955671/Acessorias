
import io
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Acessórias — Diagnóstico (Resumo + Relatórios)", layout="wide")
st.title("📊 Acessórias — Diagnóstico por Cliente")
st.caption("Inclui **Página de Resumo** e uma página só para **Ajuste de Métricas & Relatórios**.")

# ============== Helpers ==============
def read_any_csv(uploaded_file) -> pd.DataFrame:
    try:
        return pd.read_csv(uploaded_file, sep=None, engine="python")
    except Exception:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, sep=";", engine="python", encoding="utf-8", dtype=str)

def try_read_excel(uploaded_file) -> pd.DataFrame:
    try:
        return pd.read_excel(uploaded_file, dtype=str)
    except Exception:
        try:
            return pd.read_excel(uploaded_file, engine="xlrd", dtype=str)
        except Exception as e:
            st.error(f"Não consegui ler o arquivo Excel: {e}")
            raise

def parse_dates(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def to_lower_strip(df: pd.DataFrame):
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def _norm_status(x: str):
    if not isinstance(x, str):
        return x
    s = x.strip().lower()
    if s in ["concluido", "concluída", "concluida", "concluído", "finalizado", "feito"]:
        return "Concluída"
    if s in ["pendente", "em aberto", "aberto", "em andamento"]:
        return "Pendente"
    return x

def map_columns_ui(title, df: pd.DataFrame, required_map: dict, key_prefix: str):
    st.markdown(f"#### {title}")
    st.dataframe(df.head(5))
    st.write("Mapeie as colunas abaixo (use os nomes que existem na sua planilha).")
    mapped = {}
    cols = list(df.columns)
    c1, c2, c3 = st.columns(3)
    for i, (target, default_guess) in enumerate(required_map.items()):
        with [c1, c2, c3][i % 3]:
            mapped[target] = st.selectbox(
                f"Coluna para **{target}**",
                options=["<ignorar>"] + cols,
                index=(cols.index(default_guess)+1) if default_guess in cols else 0,
                key=f"{key_prefix}_{target}"
            )
    picked = {k:v for k,v in mapped.items() if v and v != "<ignorar>"}
    return picked

def apply_mapping(df: pd.DataFrame, mapping: dict):
    return df.rename(columns=mapping)

# ============== Sidebar uploads ==============
with st.sidebar:
    st.header("📂 Envio de planilhas (por cliente)")
    up_entregas = st.file_uploader("Gestão de Entregas (CSV)", type=["csv"])
    up_solic = st.file_uploader("Solicitações (XLSX/CSV)", type=["xlsx","csv"])
    up_obrig = st.file_uploader("Obrigações (XLSX/CSV)", type=["xlsx","csv"])
    up_proc = st.file_uploader("Gestão de Processos (XLSX/CSV)", type=["xlsx","csv"])
    up_resp = st.file_uploader("Responsáveis & Departamentos (XLS/XLSX/CSV)", type=["xls","xlsx","csv"])
    st.markdown("---")
    st.caption("Mapeie colunas nas abas. O **Resumo** e os **Relatórios** usam o que estiver carregado.")

# ============== Tabs ==============
tabs = st.tabs(["🏠 Resumo", "🧾 Entregas", "📨 Solicitações", "📅 Obrigações", "⚙️ Processos", "👤 Responsáveis", "📝 Relatórios", "📦 Exportações"])

# session state holders
for key in ["dfe","dfs","dfo","dfp","dfr"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ---------- Entregas ----------
with tabs[1]:
    if up_entregas:
        df_raw = read_any_csv(up_entregas)
        df_raw = to_lower_strip(df_raw)
        req_map = {
            "empresa": "empresa",
            "cnpj": "cnpj",
            "obrigacao": "obrigação / tarefa",
            "departamento": "departamento",
            "responsavel_prazo": "responsável prazo",
            "responsavel_entrega": "responsável entrega",
            "competencia": "competência",
            "data_vencimento": "vencimento",
            "data_entrega": "data entrega",
            "status": "status",
            "protocolo": "protocolo"
        }
        mapping = map_columns_ui("Mapeamento — Entregas", df_raw, req_map, "ent")
        df_ent = apply_mapping(df_raw, mapping)
        df_ent = parse_dates(df_ent, ["data_vencimento","data_entrega","competencia"])
        if "status" in df_ent.columns:
            df_ent["status"] = df_ent["status"].map(_norm_status).fillna(df_ent["status"])

        today = pd.to_datetime(date.today())
        if "data_vencimento" in df_ent.columns:
            df_ent["atrasada_concluida"] = np.where(
                (df_ent.get("status","").str.lower()=="concluída") & df_ent.get("data_entrega").notna() & (df_ent.get("data_entrega") > df_ent.get("data_vencimento")),
                True, False
            )
            df_ent["atrasada_pendente"] = np.where(
                (df_ent.get("status","").str.lower()!="concluída") & df_ent.get("data_vencimento").notna() & (today > df_ent.get("data_vencimento")),
                True, False
            )
            df_ent["em_risco"] = np.where(
                (df_ent.get("status","").str.lower()!="concluída") & df_ent.get("data_vencimento").notna() & ((df_ent.get("data_vencimento") - today).dt.days.between(0,2)),
                True, False
            )
            df_ent["pontual"] = np.where(
                (df_ent.get("status","").str.lower()=="concluída") & df_ent.get("data_entrega").notna() & (df_ent.get("data_entrega") <= df_ent.get("data_vencimento")),
                True, False
            )
            df_ent["dias_atraso"] = np.where(
                (df_ent.get("status","").str.lower()=="concluída") & df_ent.get("data_entrega").notna(),
                (df_ent.get("data_entrega") - df_ent.get("data_vencimento")).dt.days.clip(lower=0),
                np.where(
                    (df_ent.get("status","").str.lower()!="concluída") & (df_ent.get("data_vencimento").notna()),
                    (today - df_ent.get("data_vencimento")).dt.days.clip(lower=0),
                    np.nan
                )
            )
        st.session_state["dfe"] = df_ent
        st.success("Entregas carregadas e mapeadas.")
    else:
        st.info("Envie a planilha de **Gestão de Entregas** na barra lateral.")

# ---------- Solicitações ----------
with tabs[2]:
    if up_solic:
        df_raw = try_read_excel(up_solic) if up_solic.name.lower().endswith(".xlsx") else read_any_csv(up_solic)
        df_raw = to_lower_strip(df_raw)
        req_map = {
            "id": "id da solicitação",
            "assunto": "assunto",
            "empresa": "empresa",
            "status": "status",
            "prioridade": "prioridade",
            "responsavel": "responsável",
            "abertura": "abertura",
            "prazo": "prazo",
            "ultima_atualizacao": "última atualização",
            "conclusao": "conclusão"
        }
        mapping = map_columns_ui("Mapeamento — Solicitações", df_raw, req_map, "sol")
        dfr = apply_mapping(df_raw, mapping)
        dfr = parse_dates(dfr, ["abertura","prazo","ultima_atualizacao","conclusao"])
        if "status" in dfr.columns:
            dfr["status"] = dfr["status"].map(_norm_status).fillna(dfr["status"])

        today = pd.to_datetime(date.today())
        dfr["tempo_ate_conclusao_dias"] = np.where(
            dfr.get("conclusao").notna() & dfr.get("abertura").notna(),
            (dfr.get("conclusao") - dfr.get("abertura")).dt.days,
            np.nan
        )
        dfr["aberta_ha_dias"] = np.where(
            dfr.get("conclusao").isna() & dfr.get("abertura").notna(),
            (today - dfr.get("abertura")).dt.days,
            np.nan
        )
        st.session_state["dfs"] = dfr
        st.success("Solicitações carregadas e mapeadas.")
    else:
        st.info("Envie a planilha de **Solicitações** na barra lateral.")

# ---------- Obrigações ----------
with tabs[3]:
    if up_obrig:
        df_raw = try_read_excel(up_obrig) if up_obrig.name.lower().endswith(".xlsx") else read_any_csv(up_obrig)
        df_raw = to_lower_strip(df_raw)
        req_map = {
            "obrigacao": "obrigação",
            "mini": "mini",
            "departamento": "departamento",
            "responsavel": "responsável",
            "periodicidade": "periodicidade",
            "prazo_mensal": "prazo",
            "alerta_dias": "alerta"
        }
        mapping = map_columns_ui("Mapeamento — Obrigações", df_raw, req_map, "obr")
        dfo = apply_mapping(df_raw, mapping)
        st.session_state["dfo"] = dfo
        st.success("Obrigações carregadas e mapeadas.")
        if "departamento" in dfo.columns and "obrigacao" in dfo.columns:
            fig = px.treemap(dfo, path=["departamento","obrigacao"], title="Impacto por Departamento e Obrigação")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dfo.head(50))
    else:
        st.info("Envie a planilha de **Obrigações** na barra lateral.")

# ---------- Processos ----------
with tabs[4]:
    if up_proc:
        df_raw = try_read_excel(up_proc) if up_proc.name.lower().endswith(".xlsx") else read_any_csv(up_proc)
        df_raw = to_lower_strip(df_raw)
        req_map = {
            "id_processo": "id",
            "processo": "processo",
            "departamento": "departamento",
            "empresa": "empresa",
            "responsavel": "responsável",
            "inicio": "inicio",
            "conclusao": "conclusão",
            "status": "status",
            "progresso": "progresso"
        }
        mapping = map_columns_ui("Mapeamento — Processos", df_raw, req_map, "pro")
        dfp = apply_mapping(df_raw, mapping)
        dfp = parse_dates(dfp, ["inicio","conclusao"])
        if "status" in dfp.columns:
            dfp["status"] = dfp["status"].map(_norm_status).fillna(dfp["status"])
        st.session_state["dfp"] = dfp
        st.success("Processos carregados e mapeados.")
        st.dataframe(dfp.head(50))
    else:
        st.info("Envie a planilha de **Gestão de Processos** na barra lateral.")

# ---------- Responsáveis ----------
with tabs[5]:
    if up_resp:
        df_raw = try_read_excel(up_resp) if up_resp.name.lower().endswith((".xls",".xlsx")) else read_any_csv(up_resp)
        df_raw = to_lower_strip(df_raw)
        req_map = {
            "responsavel": "responsavel",
            "departamento": "departamento",
            "email": "email",
            "cargo": "cargo"
        }
        mapping = map_columns_ui("Mapeamento — Responsáveis & Departamentos", df_raw, req_map, "resp")
        dfr = apply_mapping(df_raw, mapping)
        st.session_state["dfr"] = dfr
        st.success("Responsáveis/Departamentos carregados e mapeados.")
        st.dataframe(dfr.head(50))
    else:
        st.info("Envie a planilha de **Responsáveis & Departamentos** na barra lateral.")

# ---------- 🏠 Resumo ----------
with tabs[0]:
    c1, c2, c3, c4, c5 = st.columns(5)
    if isinstance(st.session_state.get("dfe"), pd.DataFrame):
        dfe = st.session_state["dfe"]
        total_e = len(dfe)
        concluidas_e = int((dfe.get("status","").str.lower()=="concluída").sum()) if "status" in dfe else 0
        pendentes_e = total_e - concluidas_e
        atrasadas_e = int((dfe.get("atrasada_concluida", False) | dfe.get("atrasada_pendente", False)).sum()) if "atrasada_concluida" in dfe else 0
        c1.metric("Entregas (total)", f"{total_e:,}".replace(",","."))
        c2.metric("Entregas atrasadas", f"{atrasadas_e:,}".replace(",","."))
    else:
        c1.metric("Entregas (total)", "—")
        c2.metric("Entregas atrasadas", "—")
    if isinstance(st.session_state.get("dfs"), pd.DataFrame):
        dfs = st.session_state["dfs"]
        total_s = len(dfs)
        abertas_s = int(dfs.get("conclusao").isna().sum())
        c3.metric("Solicitações (total)", f"{total_s:,}".replace(",","."))
        c4.metric("Solicitações abertas", f"{abertas_s:,}".replace(",","."))
    else:
        c3.metric("Solicitações (total)", "—")
        c4.metric("Solicitações abertas", "—")
    if isinstance(st.session_state.get("dfp"), pd.DataFrame):
        dfp = st.session_state["dfp"]
        c5.metric("Processos", f"{len(dfp):,}".replace(",","."))
    else:
        c5.metric("Processos", "—")

# ---------- 📝 Relatórios ----------
with tabs[6]:
    st.subheader("⚙️ Ajuste de Métricas & Filtros")
    c1, c2, c3 = st.columns(3)
    with c1:
        dias_em_risco = st.number_input("Entregas: 'em risco' quando faltam ≤ (dias)", min_value=0, max_value=10, value=2)
        considerar_ultimos = st.number_input("Ranking de atrasos: últimos (dias)", min_value=7, max_value=120, value=30)
    with c2:
        sla_alerta = st.number_input("Solicitações: 'aberta' crítica a partir de (dias)", min_value=1, max_value=60, value=14)
        sem_update_alerta = st.number_input("Solicitações: prioridade ALTA sem atualização ≥ (dias)", min_value=1, max_value=30, value=3)
    with c3:
        proc_dias_alerta = st.number_input("Processos: em andamento crítico ≥ (dias)", min_value=7, max_value=180, value=30)

    st.markdown("##### Filtros globais (aplicados quando possível)")
    empresas = None; departamentos = None; responsaveis = None
    if isinstance(st.session_state.get("dfe"), pd.DataFrame):
        dfe = st.session_state["dfe"]
        empresas = sorted(dfe.get("empresa", pd.Series(dtype=str)).dropna().unique().tolist())
        departamentos = sorted(dfe.get("departamento", pd.Series(dtype=str)).dropna().unique().tolist())
        responsaveis = sorted(dfe.get("responsavel_entrega", pd.Series(dtype=str)).dropna().unique().tolist())
    c4, c5, c6 = st.columns(3)
    with c4:
        emp_sel = st.multiselect("Empresas (opcional)", empresas or [], default=empresas or [])
    with c5:
        dep_sel = st.multiselect("Departamentos (opcional)", departamentos or [], default=departamentos or [])
    with c6:
        resp_sel = st.multiselect("Responsáveis (opcional)", responsaveis or [], default=responsaveis or [])

    st.markdown("---")
    st.subheader("🧠 Gerar Resumo Analítico")
    gerar = st.button("Gerar relatório agora")

    if gerar:
        hoje = pd.to_datetime(date.today())
        linhas = []
        # ===== Entregas =====
        if isinstance(st.session_state.get("dfe"), pd.DataFrame):
            dfe = st.session_state["dfe"].copy()
            # aplica filtros
            if emp_sel: dfe = dfe[dfe.get("empresa").isin(emp_sel)]
            if dep_sel: dfe = dfe[dfe.get("departamento").isin(dep_sel)]
            if resp_sel: dfe = dfe[dfe.get("responsavel_entrega").isin(resp_sel)]
            # recomputa flags com parâmetros
            if "data_vencimento" in dfe.columns:
                dfe["em_risco"] = np.where(
                    (dfe.get("status","").str.lower()!="concluída") & dfe.get("data_vencimento").notna() & ((dfe.get("data_vencimento") - hoje).dt.days.between(0, dias_em_risco)),
                    True, False
                )
                dfe["atrasada_pendente"] = np.where(
                    (dfe.get("status","").str.lower()!="concluída") & dfe.get("data_vencimento").notna() & (hoje > dfe.get("data_vencimento")),
                    True, False
                )
                dfe["atrasada_concluida"] = np.where(
                    (dfe.get("status","").str.lower()=="concluída") & dfe.get("data_entrega").notna() & (dfe.get("data_entrega") > dfe.get("data_vencimento")),
                    True, False
                )
                total = len(dfe)
                concluidas = int((dfe.get("status","").str.lower()=="concluída").sum())
                pendentes = total - concluidas
                atrasadas = int((dfe["atrasada_concluida"] | dfe["atrasada_pendente"]).sum())
                em_risco_qtd = int(dfe["em_risco"].sum())
                # ranking últimos N dias
                cutoff = hoje - pd.Timedelta(days=considerar_ultimos)
                recent = dfe[dfe.get("data_vencimento") >= cutoff]
                rank_emp = pd.DataFrame()
                if not recent.empty:
                    late_recent = recent[(recent["atrasada_concluida"]) | (recent["atrasada_pendente"])]
                    if not late_recent.empty and "empresa" in late_recent.columns:
                        rank_emp = late_recent.groupby("empresa").size().reset_index(name=f"atrasos_{considerar_ultimos}d").sort_values(f"atrasos_{considerar_ultimos}d", ascending=False).head(5)

                linhas += [
                    f"### Entregas",
                    f"- Total: **{total}** | Concluídas: **{concluidas}** | Pendentes: **{pendentes}**",
                    f"- Atrasadas (inclui pendentes vencidas): **{atrasadas}**",
                    f"- Em risco (vencem em ≤ {dias_em_risco} dias): **{em_risco_qtd}**",
                ]
                if not rank_emp.empty:
                    top_lines = "\n".join([f"  - {r['empresa']}: {int(r[f'atrasos_{considerar_ultimos}d'])} atrasos" for _,r in rank_emp.iterrows()])
                    linhas += [f"- TOP atrasos (últimos {considerar_ultimos} dias):\n{top_lines}"]

        # ===== Solicitações =====
        if isinstance(st.session_state.get("dfs"), pd.DataFrame):
            dfs = st.session_state["dfs"].copy()
            if emp_sel and "empresa" in dfs.columns: dfs = dfs[dfs["empresa"].isin(emp_sel)]
            if resp_sel and "responsavel" in dfs.columns: dfs = dfs[dfs["responsavel"].isin(resp_sel)]
            hoje = pd.to_datetime(date.today())
            long_open = pd.DataFrame()
            sem_upd = pd.DataFrame()
            if {"conclusao","abertura"}.issubset(dfs.columns):
                if "aberta_ha_dias" not in dfs.columns and "abertura" in dfs.columns:
                    dfs["aberta_ha_dias"] = np.where(dfs["conclusao"].isna() & dfs["abertura"].notna(), (hoje - dfs["abertura"]).dt.days, np.nan)
                long_open = dfs[(dfs["conclusao"].isna()) & (dfs["aberta_ha_dias"] >= sla_alerta)]
            if {"prioridade","ultima_atualizacao","conclusao"}.issubset(dfs.columns):
                sem_upd = dfs[(dfs["conclusao"].isna()) & (dfs["prioridade"].str.contains("alta", case=False, na=False)) & ((hoje - dfs["ultima_atualizacao"]).dt.days >= sem_update_alerta)]
            total_s = len(dfs)
            abertas = int(dfs.get("conclusao").isna().sum()) if "conclusao" in dfs.columns else 0
            linhas += [
                f"### Solicitações",
                f"- Total: **{total_s}** | Abertas: **{abertas}**",
                f"- Críticas: Abertas ≥ {sla_alerta} dias: **{len(long_open)}** | Alta sem atualização ≥ {sem_update_alerta} dias: **{len(sem_upd)}**",
            ]

        # ===== Processos =====
        if isinstance(st.session_state.get("dfp"), pd.DataFrame):
            dfp = st.session_state["dfp"].copy()
            if emp_sel and "empresa" in dfp.columns: dfp = dfp[dfp["empresa"].isin(emp_sel)]
            if dep_sel and "departamento" in dfp.columns: dfp = dfp[dfp["departamento"].isin(dep_sel)]
            if resp_sel and "responsavel" in dfp.columns: dfp = dfp[dfp["responsavel"].isin(resp_sel)]
            hoje = pd.to_datetime(date.today())
            if {"inicio","conclusao","status"}.issubset(dfp.columns):
                dur = np.where(dfp["conclusao"].notna(), (dfp["conclusao"] - dfp["inicio"]).dt.days, (hoje - dfp["inicio"]).dt.days)
                dfp["duracao_dias"] = dur
                crit = dfp[(dfp.get("status","").str.lower()!="concluída") & (dfp["duracao_dias"] >= proc_dias_alerta)]
                linhas += [
                    f"### Processos",
                    f"- Total: **{len(dfp)}**",
                    f"- Em andamento ≥ {proc_dias_alerta} dias: **{len(crit)}**",
                ]

        if not linhas:
            st.warning("Nenhum dataset carregado para gerar relatório.")
        else:
            md = "# Resumo Analítico\n\n" + "\n".join(linhas)
            st.markdown(md)
            st.download_button("⬇️ Baixar relatório (.md)", md.encode("utf-8"), "relatorio_resumo.md", "text/markdown")

# ---------- 📦 Exportações ----------
with tabs[7]:
    st.subheader("💾 Exportações")
    for name, obj in [("entregas","dfe"), ("solicitacoes","dfs"), ("obrigacoes","dfo"), ("processos","dfp"), ("responsaveis","dfr")]:
        df = st.session_state.get(obj)
        if isinstance(df, pd.DataFrame):
            st.download_button(f"⬇️ CSV — {name}", df.to_csv(index=False).encode("utf-8"), f"{name}_tratado.csv", "text/csv")
        else:
            st.write(f"{name}: (nenhum dataset carregado)")
