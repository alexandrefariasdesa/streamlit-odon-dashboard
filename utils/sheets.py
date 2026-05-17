"""
Leitura direta do Google Sheets via service account.
Retorna DataFrames prontos para o processor.
"""
import os
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

_SA_FILE = os.path.join(os.path.dirname(__file__), "..", "service_account.json")

_IDS = {
    "vendas":               os.getenv("SHEET_VENDAS_INTERNA", "19GpwDw2rDLK5bM0SkBhqp1DJe7fmyyuYsb37Typp9Go"),
    "comercial":            os.getenv("SHEET_COMERCIAL",       "1L39PWwteu6xA7XH9_lynPqGN652gIa4SNtbcxpqgU9I"),
    "ibgp":                 os.getenv("SHEET_IBGP",            "1xY3R0uyWVAnajGxuW5EV7bHLouw0CIaHSwdziZMv9yQ"),
    "imam":                 os.getenv("SHEET_IMAM",            "1hRQgxLQroqOA6XX44OAAGWDNSiE2ZVbV3LWSW4iMmq0"),
    "ipatinga":             os.getenv("SHEET_IPATINGA",        "1ebZYBoEDEawHDo88RdnlA-Mrehk79aF4sAT0yQ9WU-Q"),
    "petrobras":            os.getenv("SHEET_PETROBRAS",       "15Etua8KJIrwYwHx5w9OQk1hfvYdCY0RMlsSFHph6tII"),
    "webinario":            os.getenv("SHEET_WEBINARIO",       "15NFxl75-FbgVyfuv6qwdwCCPki1lOfDgT8BY7aiQWPM"),
    "webinario_ipatinga":   os.getenv("SHEET_WEBINARIO_IPATINGA", "1OKVGi34FZkh8tE8W5vuSl18t3HWkiGOhtq7ANtBBMtI"),
    "ebook":                os.getenv("SHEET_EBOOK",           "1vIcWNzgUMxZYt-cau1WGAMhETL41HMRjDI6ViNAK5PQ"),
    "crm":                  os.getenv("SHEET_CRM",             "1P-wBAyOn9sYR_8JdgRA8EBeH4_-JUbnGS7lapYBu-18"),
}

_TABS = {
    "vendas":             os.getenv("TAB_VENDAS_INTERNA",        "Página1"),
    "comercial":          os.getenv("TAB_COMERCIAL",             "Página1"),
    "ibgp":               os.getenv("TAB_IBGP",                  "LEADS"),
    "imam":               os.getenv("TAB_IMAM",                  "LEADS"),
    "ipatinga":           os.getenv("TAB_IPATINGA",              "LEADS"),
    "petrobras":          os.getenv("TAB_PETROBRAS",             "LEADS"),
    "webinario":          os.getenv("TAB_WEBINARIO",             "LEADS"),
    "webinario_ipatinga": os.getenv("TAB_WEBINARIO_IPATINGA",   "LEADS"),
    "ebook":              os.getenv("TAB_EBOOK",                 "Leads"),
    "crm":                os.getenv("TAB_CRM",                   "Criação de Planilha de Leads"),
}


def _client():
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=_SCOPES
            )
            return gspread.authorize(creds)
    except Exception:
        pass
    creds = Credentials.from_service_account_file(_SA_FILE, scopes=_SCOPES)
    return gspread.authorize(creds)


def _load(key: str) -> pd.DataFrame:
    sheet_id = _IDS.get(key, "")
    tab = _TABS.get(key, "Página1")
    if not sheet_id:
        return pd.DataFrame()
    try:
        gc = _client()
        spreadsheet = gc.open_by_key(sheet_id)
        # Tenta a aba configurada; se falhar, tenta variações comuns
        ws = None
        candidates = [tab, tab.capitalize(), tab.upper(), tab.lower(), "Leads", "LEADS", "Página1", "Sheet1"]
        for candidate in candidates:
            try:
                ws = spreadsheet.worksheet(candidate)
                break
            except Exception:
                continue
        if ws is None:
            available = [w.title for w in spreadsheet.worksheets()]
            st.warning(f"Aba '{tab}' não encontrada em '{key}'. Abas disponíveis: {available}")
            return pd.DataFrame()
        # Usa get_all_values para evitar erro com cabeçalhos duplicados/vazios
        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:
            return pd.DataFrame()
        headers = all_values[0]
        # Deduplica cabeçalhos vazios
        seen: dict = {}
        clean_headers = []
        for h in headers:
            h = h.strip()
            if not h:
                h = f"_col_{len(clean_headers)}"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else:
                seen[h] = 0
            clean_headers.append(h)
        return pd.DataFrame(all_values[1:], columns=clean_headers)
    except Exception as e:
        st.warning(f"Erro ao ler '{key}': {e}")
        return pd.DataFrame()


# ── Vendas (Hotmart interno) ──────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_vendas() -> pd.DataFrame:
    """
    Lê SHEET_VENDAS_INTERNA e retorna no formato esperado por parse_compras_sheet.
    Colunas retornadas: USUARIO, EMAIL, TELEFONE, DT APROVACAO, VALOR PAGO, PRODUTO, UTM SOURCE
    """
    df = _load("vendas")
    if df.empty:
        return df

    df.columns = [c.strip() for c in df.columns]

    # Detectar colunas dinamicamente
    col_map = {}
    for col in df.columns:
        cn = col.strip().lower()
        if cn in ("nome", "name", "usuario"):
            col_map[col] = "USUARIO"
        elif cn in ("email",):
            col_map[col] = "EMAIL"
        elif "tel" in cn or "whats" in cn or "phone" in cn or "celul" in cn:
            col_map[col] = "TELEFONE"
        elif "cria" in cn or cn in ("compra_em", "data", "created_at", "dt aprovacao", "data_compra"):
            col_map[col] = "DT APROVACAO"
        elif cn in ("valor", "valor_num", "preco", "price", "valor pago"):
            col_map[col] = "VALOR PAGO"
        elif "produto" in cn or "product" in cn:
            col_map[col] = "PRODUTO"
        elif "utm" in cn and "source" in cn:
            col_map[col] = "UTM SOURCE"
        elif "pagamento" in cn or "payment" in cn:
            col_map[col] = "PAGAMENTO"

    df = df.rename(columns=col_map)

    for col in ("USUARIO", "EMAIL", "TELEFONE", "DT APROVACAO", "VALOR PAGO", "PRODUTO", "UTM SOURCE"):
        if col not in df.columns:
            df[col] = ""

    # UTM SOURCE fallback: usa PAGAMENTO se disponível
    if "PAGAMENTO" in df.columns and (df["UTM SOURCE"] == "").all():
        df["UTM SOURCE"] = df["PAGAMENTO"]

    return df


# ── Planilha Comercial / UTM ──────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_comercial() -> pd.DataFrame:
    """
    Lê SHEET_COMERCIAL e retorna no formato esperado por parse_leads_comercial_sheet.
    Colunas: NOME, E-MAIL / EDITAL, TELEFONE, UTM_SOURCE, UTM_MEDIUM, UTM_CAMPAIGN, DATA
    """
    df = _load("comercial")
    if df.empty:
        return df

    df.columns = [c.strip() for c in df.columns]

    col_map = {}
    for col in df.columns:
        cn = col.strip().lower()
        if cn in ("nome", "name"):
            col_map[col] = "NOME"
        elif "e-mail" in cn or cn in ("email", "edital", "e-mail / edital"):
            col_map[col] = "E-MAIL / EDITAL"
        elif "tel" in cn or "whats" in cn or "phone" in cn or "celul" in cn:
            col_map[col] = "TELEFONE"
        elif cn in ("utm_source", "utm source"):
            col_map[col] = "UTM_SOURCE"
        elif cn in ("utm_medium", "utm medium"):
            col_map[col] = "UTM_MEDIUM"
        elif cn in ("utm_campaign", "utm campaign"):
            col_map[col] = "UTM_CAMPAIGN"
        elif cn in ("data", "date", "created_at", "criado_em", "timestamp"):
            col_map[col] = "DATA"
        elif "mensagem" in cn or "message" in cn or "msg" in cn:
            col_map[col] = "MENSAGEM"

    df = df.rename(columns=col_map)

    for col in ("NOME", "E-MAIL / EDITAL", "TELEFONE", "UTM_SOURCE", "UTM_MEDIUM", "DATA"):
        if col not in df.columns:
            df[col] = ""

    return df


# ── Leads por funil ───────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_leads_funil(funil: str) -> pd.DataFrame:
    """Retorna DataFrame de leads de um funil específico."""
    return _load(funil)


# ── Ebook ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_ebook() -> pd.DataFrame:
    """Retorna DataFrame de compradores do ebook."""
    return _load("ebook")


# ── CRM WhatsApp Comercial ────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def get_crm() -> pd.DataFrame:
    """
    Lê SHEET_CRM (planilha de leads CRM WhatsApp comercial).
    Colunas esperadas: nome, data, telefone, mensagem, status, respondeu, email
    """
    df = _load("crm")
    if df.empty:
        return df

    df.columns = [c.strip() for c in df.columns]

    col_map = {}
    for col in df.columns:
        cn = col.strip().lower()
        if cn in ("nome", "name"):
            col_map[col] = "NOME"
        elif cn in ("email", "e-mail"):
            col_map[col] = "EMAIL"
        elif "tel" in cn or "whats" in cn or "phone" in cn or "celul" in cn:
            col_map[col] = "TELEFONE"
        elif cn in ("data", "date", "created_at", "criado_em", "timestamp", "dt"):
            col_map[col] = "DATA"
        elif "mensagem" in cn or "message" in cn or "msg" in cn:
            col_map[col] = "MENSAGEM"
        elif "status" in cn:
            col_map[col] = "STATUS"
        elif "respondeu" in cn or "replied" in cn:
            col_map[col] = "RESPONDEU"
        elif any(p in cn for p in ("ganho", "perda", "resultado", "fechou", "converteu", "negoc")):
            col_map[col] = "RESULTADO"
        elif any(p in cn for p in ("motivo", "reason", "porque", "por que", "razao", "razão")):
            col_map[col] = "MOTIVO"
        elif any(p in cn for p in ("funil", "funnel", "campanha", "campaign")):
            col_map[col] = "FUNIL"
        elif any(p in cn for p in ("edital", "concurso", "interesse", "interest", "prova")):
            col_map[col] = "EDITAL"
        elif any(p in cn for p in ("origem", "canal", "origin", "source")) and "utm" not in cn:
            col_map[col] = "ORIGEM"

    df = df.rename(columns=col_map)

    for col in ("NOME", "EMAIL", "TELEFONE", "DATA", "MENSAGEM", "STATUS", "RESPONDEU",
                "RESULTADO", "MOTIVO", "FUNIL", "EDITAL", "ORIGEM"):
        if col not in df.columns:
            df[col] = ""

    return df
