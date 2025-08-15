
import io
import os
import csv
import sqlite3
from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Acessórias — Diagnóstico Unificado", layout="wide")

st.title("📊 Acessórias — Diagnóstico Unificado por Cliente")
st.caption("Envie as planilhas exportadas para cada cliente. O app permite **mapear colunas** e gera **métricas** unificadas.")

# ===================== Helpers =====================

def read_any_csv(uploaded_file) -> pd.DataFrame:
    # tenta inferir separador e encoding
    try:
        return pd.read_csv(uploaded_file, sep=None, engine="python")
    except Exception:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, sep=";", engine="python", encoding="utf-8", dtype=str)

def try_read_excel(uploaded_file) -> pd.DataFrame:
    # tenta openpyxl; se falhar, tenta xlrd (xls)
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
    df.columns = [str(c).strip() for c in df.columns]
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
            mapped[target] = st.selectbox(f"Coluna para **{target}**", options=["<ignorar>"] + cols, index=(cols.index(default_guess)+1) if default_guess in cols else 0, key=f"{key_prefix}_{target}")
    # filtra ignorados
    picked = {k:v for k,v in mapped.items() if v and v != "<ignorar>"}
    return picked

def apply_mapping(df: pd.DataFrame, mapping: dict):
    return df.rename(columns=mapping)

# ===================== Sidebar: Upload =====================

with st.sidebar:
    st.header("📂 Envio de planilhas (por cliente)")
    st.markdown("Envie as planilhas que você tiver. O que faltar é opcional.")
    up_entregas = st.file_uploader("Gestão de Entregas (CSV)", type=["csv"])
    up_solic = st.file_uploader("Solicitações (XLSX/CSV)", type=["xlsx","csv"])
    up_obrig = st.file_uploader("Obrigações (XLSX/CSV)", type=["xlsx","csv"])
    up_proc = st.file_uploader("Gestão de Processos (XLSX/CSV)", type=["xlsx","csv"])
    up_resp = st.file_uploader("Responsáveis & Departamentos (XLS/XLSX/CSV)", type=["xls","xlsx","csv"])

    st.markdown("---")
    st.caption("Dica: você pode salvar um **preset** de mapeamentos por cliente (aba Exportações).")

# ===================== Load & map each dataset =====================

tabs = st.tabs(["🧾 Entregas", "📨 Solicitações", "📅 Obrigações", "⚙️ Processos", "👤 Responsáveis", "📦 Exportações"])

# ---------- Entregas ----------
with tabs[0]:
    if up_entregas:
        df_raw = read_any_csv(up_entregas)
        df_raw = to_lower_strip(df_raw)
        # Required targets & guesses
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
        # normalize
        date_cols = ["data_vencimento","data_entrega","competencia"]
        df_ent = parse_dates(df_ent, [c for c in date_cols if c in df_ent.columns])
        if "status" in df_ent.columns:
            df_ent["status"] = df_ent["status"].map(_norm_status).fillna(df_ent["status"])
        # business logic
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
            df_ent["pontual"] = np.where(
                (df_ent.get("status","").str.lower()=="concluída") & df_ent.get("data_entrega").notna() & (df_ent.get("data_entrega") <= df_ent.get("data_vencimento")),
                True, False
            )
            df_ent["dias_atraso"] = np.where(
                (df_ent.get("status","").str.lower()=="concluída") & df_ent.get("data_entrega").notna(),
                (df_ent.get("data_entrega") - df_ent.get("data_vencimento")).dt.days.clip(lower=0),
                np.where(
                    (df_ent.get("status","").str.lower()!="concluída") & df_ent.get("data_vencimento").notna(),
                    (today - df_ent.get("data_vencimento")).dt.days.clip(lower=0),
                    np.nan
                )
            )
        # filters
        st.markdown("##### Filtros")
        emp = sorted(df_ent.get("empresa", pd.Series(dtype=str)).dropna().unique().tolist())
        dep = sorted(df_ent.get("departamento", pd.Series(dtype=str)).dropna().unique().tolist())
        res = sorted(df_ent.get("responsavel_entrega", pd.Series(dtype=str)).dropna().unique().tolist())
        c1, c2, c3 = st.columns(3)
        with c1:
            emp_sel = st.multiselect("Empresas", emp, default=emp)
        with c2:
            dep_sel = st.multiselect("Departamentos", dep, default=dep)
        with c3:
            res_sel = st.multiselect("Responsáveis (entrega)", res, default=res)
        mask = pd.Series(True, index=df_ent.index)
        if emp: mask &= df_ent["empresa"].isin(emp_sel)
        if dep: mask &= df_ent["departamento"].isin(dep_sel)
        if res: mask &= df_ent["responsavel_entrega"].isin(res_sel)
        dfe = df_ent[mask].copy()

        # KPIs
        total = len(dfe)
        concluidas = int((dfe.get("status","").str.lower()=="concluída").sum()) if "status" in dfe else 0
        pendentes = total - concluidas
        atrasadas = int((dfe.get("atrasada_concluida", False) | dfe.get("atrasada_pendente", False)).sum()) if "atrasada_concluida" in dfe else 0
        pontuais = int(dfe.get("pontual", False).sum()) if "pontual" in dfe else 0
        pontualidade = (pontuais / max(concluidas,1))*100 if concluidas else 0.0

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total", f"{total:,}".replace(",","."))
        k2.metric("Concluídas", f"{concluidas:,}".replace(",","."))
        k3.metric("Pendentes", f"{pendentes:,}".replace(",","."))
        k4.metric("Atrasadas", f"{atrasadas:,}".replace(",","."))
        k5.metric("Pontualidade (%)", f"{pontualidade:,.1f}".replace(",","."))

        st.markdown("---")
        st.subheader("🏢 Empresas com envios fora do prazo")
        if "dias_atraso" in dfe.columns:
            late = dfe[(dfe.get("atrasada_concluida", False)) | (dfe.get("atrasada_pendente", False))].copy()
            if not late.empty and "empresa" in late.columns:
                grp = late.groupby("empresa", as_index=False).agg(
                    tarefas_atrasadas=("empresa","count"),
                    atraso_medio_dias=("dias_atraso","mean"),
                    ultimo_vencimento=("data_vencimento","max")
                ).sort_values(["tarefas_atrasadas","atraso_medio_dias"], ascending=[False, False])
                st.dataframe(grp.style.format({"tarefas_atrasadas":"{:,.0f}","atraso_medio_dias":"{:,.1f}"}))
                st.download_button("⬇️ CSV — Empresas atrasadas", grp.to_csv(index=False).encode("utf-8"), "empresas_atrasadas.csv","text/csv")
            else:
                st.info("Sem dados suficientes para ranking de atraso.")

        st.markdown("#### 🔎 Tarefas atrasadas (detalhe)")
        cols_show = [c for c in ["empresa","obrigacao","departamento","responsavel_entrega","competencia","data_vencimento","data_entrega","status","dias_atraso","protocolo"] if c in dfe.columns]
        if "dias_atraso" in dfe.columns:
            late_detail = dfe[(dfe.get("atrasada_concluida", False)) | (dfe.get("atrasada_pendente", False))][cols_show].sort_values(["empresa","dias_atraso"], ascending=[True, False])
            st.dataframe(late_detail)
            st.download_button("⬇️ CSV — Tarefas atrasadas", late_detail.to_csv(index=False).encode("utf-8"), "tarefas_atrasadas.csv", "text/csv")

        st.markdown("---")
        st.subheader("📈 Visões gráficas")
        if "empresa" in dfe.columns:
            fig1 = px.bar(dfe.groupby("empresa").size().reset_index(name="tarefas"), x="empresa", y="tarefas", title="Tarefas por empresa")
            st.plotly_chart(fig1, use_container_width=True)
        if "status" in dfe.columns and "empresa" in dfe.columns:
            done = dfe[dfe["status"].str.lower()=="concluída"].copy()
            if not done.empty and "data_entrega" in done.columns:
                done["mes"] = done["data_entrega"].dt.to_period("M").astype(str)
                thr = done.groupby("mes").size().reset_index(name="concluidas")
                fig3 = px.line(thr, x="mes", y="concluidas", markers=True, title="Throughput mensal (concluídas)")
                st.plotly_chart(fig3, use_container_width=True)
        if "dias_atraso" in dfe.columns:
            aging = dfe[dfe["dias_atraso"].fillna(0) > 0]
            if not aging.empty:
                fig4 = px.histogram(aging, x="dias_atraso", nbins=20, title="Distribuição de atraso (dias)")
                st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Envie a planilha de **Gestão de Entregas** na barra lateral.")

# ---------- Solicitações ----------
with tabs[1]:
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

        st.markdown("##### Filtros")
        emp = sorted(dfr.get("empresa", pd.Series(dtype=str)).dropna().unique().tolist())
        res = sorted(dfr.get("responsavel", pd.Series(dtype=str)).dropna().unique().tolist())
        c1, c2 = st.columns(2)
        with c1:
            emp_sel = st.multiselect("Empresas", emp, default=emp)
        with c2:
            res_sel = st.multiselect("Responsáveis", res, default=res)
        mask = pd.Series(True, index=dfr.index)
        if emp: mask &= dfr["empresa"].isin(emp_sel)
        if res: mask &= dfr["responsavel"].isin(res_sel)
        dfs = dfr[mask].copy()

        # SLA simples
        dfs["tempo_ate_conclusao_dias"] = np.where(
            dfs.get("conclusao").notna() & dfs.get("abertura").notna(),
            (dfs.get("conclusao") - dfs.get("abertura")).dt.days,
            np.nan
        )
        dfs["aberta_ha_dias"] = np.where(
            dfs.get("conclusao").isna() & dfs.get("abertura").notna(),
            (pd.to_datetime(date.today()) - dfs.get("abertura")).dt.days,
            np.nan
        )

        total = len(dfs)
        concluidas = int((dfs.get("status","").str.lower()=="concluída").sum()) if "status" in dfs else 0
        abertas = total - concluidas
        sla_medio = float(np.nanmean(dfs["tempo_ate_conclusao_dias"])) if "tempo_ate_conclusao_dias" in dfs else np.nan

        k1, k2, k3 = st.columns(3)
        k1.metric("Total", f"{total:,}".replace(",","."))
        k2.metric("Concluídas", f"{concluidas:,}".replace(",","."))
        k3.metric("SLA médio (dias)", f"{sla_medio:,.1f}".replace(",","."))

        st.markdown("---")
        st.subheader("🔎 Detalhe das Solicitações")
        show_cols = [c for c in ["id","assunto","empresa","prioridade","responsavel","abertura","prazo","ultima_atualizacao","conclusao","status","tempo_ate_conclusao_dias","aberta_ha_dias"] if c in dfs.columns]
        st.dataframe(dfs[show_cols])
    else:
        st.info("Envie a planilha de **Solicitações** na barra lateral.")

# ---------- Obrigações ----------
with tabs[2]:
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

        st.subheader("📅 Calendário/Matriz de Obrigações")
        if "departamento" in dfo.columns and "obrigacao" in dfo.columns:
            fig = px.treemap(dfo, path=["departamento","obrigacao"], title="Impacto por Departamento e Obrigação")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dfo.head(50))
    else:
        st.info("Envie a planilha de **Obrigações** na barra lateral.")

# ---------- Processos ----------
with tabs[3]:
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

        st.markdown("##### Filtros")
        emp = sorted(dfp.get("empresa", pd.Series(dtype=str)).dropna().unique().tolist())
        dep = sorted(dfp.get("departamento", pd.Series(dtype=str)).dropna().unique().tolist())
        res = sorted(dfp.get("responsavel", pd.Series(dtype=str)).dropna().unique().tolist())
        c1, c2, c3 = st.columns(3)
        with c1:
            emp_sel = st.multiselect("Empresas", emp, default=emp)
        with c2:
            dep_sel = st.multiselect("Departamentos", dep, default=dep)
        with c3:
            res_sel = st.multiselect("Responsáveis", res, default=res)
        mask = pd.Series(True, index=dfp.index)
        if emp: mask &= dfp["empresa"].isin(emp_sel)
        if dep: mask &= dfp["departamento"].isin(dep_sel)
        if res: mask &= dfp["responsavel"].isin(res_sel)
        dfp = dfp[mask].copy()

        total = len(dfp)
        concluidos = int((dfp.get("status","").str.lower()=="concluída").sum()) if "status" in dfp else 0
        em_andamento = total - concluidos
        duracao_media = float(np.nanmean((dfp.get("conclusao") - dfp.get("inicio")).dt.days)) if ("inicio" in dfp and "conclusao" in dfp) else np.nan

        k1, k2, k3 = st.columns(3)
        k1.metric("Processos", f"{total:,}".replace(",","."))
        k2.metric("Concluídos", f"{concluidos:,}".replace(",","."))
        k3.metric("Duração média (dias)", f"{duracao_media:,.1f}".replace(",","."))

        st.markdown("---")
        if "departamento" in dfp.columns:
            fig5 = px.bar(dfp.groupby("departamento").size().reset_index(name="qtd"), x="departamento", y="qtd", title="Processos por Departamento")
            st.plotly_chart(fig5, use_container_width=True)

        st.subheader("🔎 Detalhe dos Processos")
        show_cols = [c for c in ["id_processo","processo","empresa","departamento","responsavel","inicio","conclusao","status","progresso"] if c in dfp.columns]
        st.dataframe(dfp[show_cols])
    else:
        st.info("Envie a planilha de **Gestão de Processos** na barra lateral.")

# ---------- Responsáveis / Departamentos ----------
with tabs[4]:
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
        st.dataframe(dfr.head(50))
    else:
        st.info("Envie a planilha de **Responsáveis & Departamentos** na barra lateral.")

# ---------- Exportações & Presets ----------
with tabs[5]:
    st.subheader("💾 Exportações")
    st.write("Você pode exportar os datasets tratados em CSV para arquivar junto do diagnóstico.")
    # Simple session stores for export if exist
    for name, var in [("entregas","dfe"), ("solicitacoes","dfs"), ("obrigacoes","dfo"), ("processos","dfp"), ("responsaveis","dfr")]:
        if name in globals():
            df = globals()[name[0:3]+'e'] if name=="entregas" else globals().get(name[0:3]+'s') if name=="solicitacoes" else globals().get(name[0:3]+'o') if name=="obrigacoes" else globals().get(name[0:3]+'p') if name=="processos" else globals().get(name[0:3]+'r')
        else:
            df = None
        if isinstance(df, pd.DataFrame):
            st.download_button(f"⬇️ CSV — {name}", df.to_csv(index=False).encode("utf-8"), f"{name}_tratado.csv", "text/csv")

    st.markdown("---")
    st.subheader("⚙️ Preset de mapeamentos por cliente")
    st.caption("Salve um JSON de mapeamentos (por aba) para reutilizar ao diagnosticar o mesmo cliente no futuro.")
    preset_name = st.text_input("Nome do preset (ex.: Cliente X - Agosto/2025)")
    if st.button("Salvar preset (JSON)"):
        st.warning("Para simplificar, copie manualmente as escolhas de cada select e salve localmente um JSON com os nomes. (Versão básica)")

st.caption("Feito para processar planilhas que **mudam a cada cliente**. Ajuste mapeamentos e gere métricas em poucos cliques.")
