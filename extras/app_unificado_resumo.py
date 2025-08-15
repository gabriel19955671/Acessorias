
import io
import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Acessórias — Diagnóstico Unificado (com Resumo)", layout="wide")

st.title("📊 Acessórias — Diagnóstico Unificado por Cliente")
st.caption("Versão com **Página de Resumo**: destaques e 'dados perigosos' para agir rápido.")

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
    st.caption("Dica: mapeie colunas nas abas; o **Resumo** usa o que estiver carregado.")

# ============== Tabs (Resumo + abas originais) ==============

tabs = st.tabs(["🏠 Resumo", "🧾 Entregas", "📨 Solicitações", "📅 Obrigações", "⚙️ Processos", "👤 Responsáveis", "📦 Exportações"])

# session state holders
for key in ["dfe","dfs","dfo","dfp","dfr"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ---------- 🧾 Entregas ----------
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
                    (df_ent.get("status","").str.lower()!="concluída") & df_ent.get("data_vencimento").notna(),
                    (today - df_ent.get("data_vencimento")).dt.days.clip(lower=0),
                    np.nan
                )
            )
        # Save to session
        st.session_state["dfe"] = df_ent
        st.success("Entregas carregadas e mapeadas.")
    else:
        st.info("Envie a planilha de **Gestão de Entregas** na barra lateral.")

# ---------- 📨 Solicitações ----------
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
        # Enrich
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
        # Save
        st.session_state["dfs"] = dfr
        st.success("Solicitações carregadas e mapeadas.")
    else:
        st.info("Envie a planilha de **Solicitações** na barra lateral.")

# ---------- 📅 Obrigações ----------
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

# ---------- ⚙️ Processos ----------
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

# ---------- 👤 Responsáveis ----------
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

# ---------- 🏠 RESUMO ----------
with tabs[0]:
    st.subheader("🔎 Visão Geral (KPIs)")
    c1, c2, c3, c4, c5 = st.columns(5)
    # Entregas KPIs
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

    # Solicitações KPIs
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

    st.markdown("---")
    st.subheader("🚨 Dados perigosos (prioridades de ação)")

    # 1) Entregas em risco (vencem em até 2 dias) e pendentes vencidas
    if isinstance(st.session_state.get("dfe"), pd.DataFrame):
        dfe = st.session_state["dfe"]
        hoje = pd.to_datetime(date.today())
        perigosas = pd.DataFrame()
        if {"empresa","obrigacao","data_vencimento","status"}.issubset(dfe.columns):
            em_risco = dfe[(dfe.get("status","").str.lower()!="concluída") & (dfe.get("data_vencimento").notna()) & ((dfe.get("data_vencimento") - hoje).dt.days.between(0,2))]
            vencidas = dfe[(dfe.get("status","").str.lower()!="concluída") & (dfe.get("data_vencimento").notna()) & (hoje > dfe.get("data_vencimento"))]
            perigosas = pd.concat([em_risco.assign(_flag="EM RISCO (≤2 dias)"),
                                   vencidas.assign(_flag="PENDENTE VENCIDA")], ignore_index=True)
        if not perigosas.empty:
            st.markdown("**Entregas críticas (seleção)**")
            show_cols = [c for c in ["_flag","empresa","obrigacao","departamento","responsavel_entrega","competencia","data_vencimento","status","dias_atraso","protocolo"] if c in perigosas.columns]
            st.dataframe(perigosas.sort_values(["_flag","data_vencimento"]).head(200)[show_cols])
        else:
            st.info("Sem entregas críticas identificadas.")
    else:
        st.info("Carregue **Entregas** para ver riscos de prazo.")

    st.markdown("---")

    # 2) Empresas com maior volume de atrasos (últimos 30 dias)
    if isinstance(st.session_state.get("dfe"), pd.DataFrame) and "data_vencimento" in st.session_state["dfe"].columns:
        dfe = st.session_state["dfe"].copy()
        cutoff = pd.to_datetime(date.today()) - pd.Timedelta(days=30)
        recent = dfe[dfe["data_vencimento"] >= cutoff]
        if not recent.empty:
            late_recent = recent[(recent.get("atrasada_concluida", False)) | (recent.get("atrasada_pendente", False))]
            if not late_recent.empty and "empresa" in late_recent.columns:
                rank_emp = late_recent.groupby("empresa").size().reset_index(name="atrasos_30d").sort_values("atrasos_30d", ascending=False).head(10)
                st.markdown("**TOP empresas com atrasos nos últimos 30 dias**")
                st.dataframe(rank_emp)
        else:
            st.info("Sem dados recentes (30 dias) para ranking de atrasos.")
    else:
        st.info("Carregue **Entregas** para ver ranking de atrasos.")

    st.markdown("---")

    # 3) Solicitações abertas há muito tempo / prioridade alta sem atualização
    if isinstance(st.session_state.get("dfs"), pd.DataFrame):
        dfs = st.session_state["dfs"]
        hoje = pd.to_datetime(date.today())
        perigos_solic = pd.DataFrame()
        if "aberta_ha_dias" in dfs.columns:
            long_open = dfs[(dfs["conclusao"].isna()) & (dfs["aberta_ha_dias"] >= 14)]
            perigos_solic = pd.concat([perigos_solic, long_open.assign(_flag="ABERTA ≥14 dias")])
        if {"prioridade","ultima_atualizacao"}.issubset(dfs.columns):
            sem_upd = dfs[(dfs["conclusao"].isna()) & (dfs["prioridade"].str.contains("alta", case=False, na=False)) & ((hoje - dfs["ultima_atualizacao"]).dt.days >= 3)]
            perigos_solic = pd.concat([perigos_solic, sem_upd.assign(_flag="PRIORIDADE ALTA sem atualização ≥3 dias")])
        if not perigos_solic.empty:
            st.markdown("**Solicitações críticas (seleção)**")
            show_cols = [c for c in ["_flag","id","assunto","empresa","prioridade","responsavel","abertura","prazo","ultima_atualizacao","status","aberta_ha_dias","tempo_ate_conclusao_dias"] if c in perigos_solic.columns]
            st.dataframe(perigos_solic.sort_values(["_flag","abertura"]).head(200)[show_cols])
        else:
            st.info("Sem solicitações críticas identificadas.")
    else:
        st.info("Carregue **Solicitações** para ver riscos de SLA.")

    st.markdown("---")

    # 4) Processos estourando prazo (p.ex. >30 dias em andamento)
    if isinstance(st.session_state.get("dfp"), pd.DataFrame):
        dfp = st.session_state["dfp"]
        hoje = pd.to_datetime(date.today())
        if {"inicio","conclusao","status"}.issubset(dfp.columns):
            dur = np.where(dfp["conclusao"].notna(), (dfp["conclusao"] - dfp["inicio"]).dt.days,
                          (hoje - dfp["inicio"]).dt.days)
            dfp2 = dfp.copy()
            dfp2["duracao_dias"] = dur
            crit = dfp2[(dfp2.get("status","").str.lower()!="concluída") & (dfp2["duracao_dias"] >= 30)]
            if not crit.empty:
                st.markdown("**Processos críticos (em andamento ≥30 dias)**")
                show_cols = [c for c in ["id_processo","processo","empresa","departamento","responsavel","inicio","conclusao","status","duracao_dias","progresso"] if c in dfp2.columns]
                st.dataframe(crit.sort_values("duracao_dias", ascending=False).head(200)[show_cols])
            else:
                st.info("Sem processos críticos identificados.")
        else:
            st.info("Para análise de processos críticos, mapeie início/conclusão/status.")
    else:
        st.info("Carregue **Processos** para ver riscos de execução.")

# ---------- 📦 Exportações ----------
with tabs[6]:
    st.subheader("💾 Exportações")
    for name, obj in [("entregas","dfe"), ("solicitacoes","dfs"), ("obrigacoes","dfo"), ("processos","dfp"), ("responsaveis","dfr")]:
        df = st.session_state.get(obj)
        if isinstance(df, pd.DataFrame):
            st.download_button(f"⬇️ CSV — {name}", df.to_csv(index=False).encode("utf-8"), f"{name}_tratado.csv", "text/csv")
        else:
            st.write(f"{name}: (nenhum dataset carregado)")

st.caption("Resumo foca no que **exige ação imediata**: prazos em risco, pendências vencidas, SLA estourado e processos travados.")
