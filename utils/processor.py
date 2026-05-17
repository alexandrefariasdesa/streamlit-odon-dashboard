"""
Utilities para processamento de dados Odon Concursos.
Cruzamento multi-funil por email, telefone e nome.
"""
import pandas as pd
import re
import unicodedata
from datetime import datetime


STOPWORDS = {'de', 'da', 'do', 'das', 'dos', 'e'}
COMMON_LAST = {
    'silva', 'santos', 'souza', 'sousa', 'pereira', 'oliveira', 'costa',
    'lima', 'ferreira', 'rodrigues', 'alves', 'gomes', 'ribeiro',
    'carvalho', 'almeida', 'lopes', 'martins', 'fernandes', 'barbosa'
}


def clean_email(x):
    """Normaliza e-mail (lower + strip)."""
    if pd.isna(x):
        return ''
    e = str(x).lower().strip()
    return e if e and e != 'nan' else ''


def clean_phone(x):
    """Limpa telefone: só dígitos, remove DDI 55, mantém últimos 11."""
    if pd.isna(x):
        return ''
    s = re.sub(r'\D', '', str(x))
    if len(s) > 11 and s.startswith('55'):
        s = s[2:]
    if len(s) > 11:
        s = s[-11:]
    return s if s else ''


def remove_accent(s):
    s = unicodedata.normalize('NFD', str(s))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def norm_nome(n):
    """Nome normalizado: lower, sem acentos, espaços únicos."""
    if pd.isna(n) or not n:
        return ''
    n = remove_accent(str(n).lower().strip())
    return re.sub(r'\s+', ' ', n)


def tokenize_nome(n):
    """Split nome em tokens sem stopwords."""
    return [p for p in str(n).split() if p not in STOPWORDS and len(p) > 1]


def nome_forte_match(nc, nl):
    """
    Match por nome forte: primeiro nome igual + pelo menos um sobrenome
    distintivo (não comum) em comum.
    """
    tc = tokenize_nome(nc)
    tl = tokenize_nome(nl)
    if len(tc) < 2 or len(tl) < 2:
        return False
    if tc[0] != tl[0]:
        return False
    overlap = set(tc[1:]) & set(tl[1:])
    if not overlap:
        return False
    raros = overlap - COMMON_LAST
    return bool(raros)


def extract_ddd_from_phone(phone_clean):
    """Extrai DDD (2 primeiros dígitos) de um telefone limpo."""
    if phone_clean and len(phone_clean) >= 10:
        return phone_clean[:2]
    return ''


def parse_compras_hotmart(file_obj, periodo_inicio=None, periodo_fim=None):
    """
    Carrega CSV de Compras Aprovadas do Hotmart e retorna DataFrame
    processado. Aceita filtro de período.
    """
    df = pd.read_csv(file_obj)
    df['DT'] = pd.to_datetime(df['DT APROVACAO'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    df['VALOR_NUM'] = (
        df['VALOR PAGO'].astype(str)
        .str.replace('R$', '', regex=False)
        .str.replace(' ', '')
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .astype(float)
    )
    df['EMAIL_CLEAN'] = df['EMAIL'].apply(clean_email)
    df['PHONE_CLEAN'] = df['TELEFONE'].apply(clean_phone) if 'TELEFONE' in df.columns else ''
    df['NOME_NORM'] = df['USUARIO'].apply(norm_nome)
    df['DDD'] = df['PHONE_CLEAN'].apply(extract_ddd_from_phone)

    if periodo_inicio and periodo_fim:
        ts_ini = pd.Timestamp(periodo_inicio)
        ts_fim = pd.Timestamp(periodo_fim) + pd.Timedelta(days=1)
        mask = (df["DT"] >= ts_ini) & (df["DT"] < ts_fim)
        df = df[mask & (df["VALOR_NUM"] > 0)].copy()

    return df


def parse_leads_comercial(file_obj):
    """Carrega CSV LEADS_COMERCIAL e normaliza."""
    df = pd.read_csv(file_obj)
    if 'DATA' in df.columns:
        df['DT'] = pd.to_datetime(df['DATA'], errors='coerce', utc=True).dt.tz_localize(None)
    df['EMAIL_CLEAN'] = df.get('E-MAIL / EDITAL', '').apply(clean_email) if 'E-MAIL / EDITAL' in df.columns else ''
    df['PHONE_CLEAN'] = df['TELEFONE'].apply(clean_phone) if 'TELEFONE' in df.columns else ''
    df['NOME_NORM'] = df['NOME'].apply(norm_nome) if 'NOME' in df.columns else ''
    return df


def parse_leads_funil(file_obj):
    """
    Carrega CSV genérico de leads de funil (IBGP/IMAM/Ipatinga/etc).
    Detecta colunas comuns: nome, email, telefone, DDD.
    """
    df = pd.read_csv(file_obj)
    # Detectar coluna de nome
    name_col = next((c for c in df.columns if c.upper() in ['NOME', 'NAME', 'NOME_COMPLETO']), None)
    email_col = next((c for c in df.columns if 'EMAIL' in c.upper() or 'E-MAIL' in c.upper()), None)
    phone_col = next((c for c in df.columns if 'TELEFONE' in c.upper() or 'PHONE' in c.upper() or 'WHATSAPP' in c.upper()), None)
    date_col = next((c for c in df.columns if c.upper() in ['DATA', 'DATE', 'CRIADO_EM', 'CREATED_AT']), None)

    if name_col:
        df['NOME_NORM'] = df[name_col].apply(norm_nome)
    else:
        df['NOME_NORM'] = ''
    df['EMAIL_CLEAN'] = df[email_col].apply(clean_email) if email_col else ''
    df['PHONE_CLEAN'] = df[phone_col].apply(clean_phone) if phone_col else ''
    df['DDD'] = df['PHONE_CLEAN'].apply(extract_ddd_from_phone)
    if date_col:
        df['DT'] = pd.to_datetime(df[date_col], errors='coerce')
    return df


def parse_ebook_xls(file_obj, periodo_inicio=None, periodo_fim=None):
    """Carrega XLS de sales history Hotmart (Ebook 500)."""
    df = pd.read_excel(file_obj)
    df['DT_VENDA'] = pd.to_datetime(df['Data de Venda'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    df['EMAIL_CLEAN'] = df['Email'].apply(clean_email)
    df['NOME_NORM'] = df['Nome'].apply(norm_nome)

    def join_phone(row):
        ddd = str(int(row['DDD'])) if pd.notna(row.get('DDD')) else ''
        tel = str(int(row['Telefone'])) if pd.notna(row.get('Telefone')) else ''
        return clean_phone(ddd + tel)

    df['PHONE_CLEAN'] = df.apply(join_phone, axis=1)

    df = df[df['Status'].isin(['Aprovado', 'Completo'])].copy()
    if periodo_inicio and periodo_fim:
        mask = (df['DT_VENDA'].dt.date >= periodo_inicio) & (df['DT_VENDA'].dt.date <= periodo_fim)
        df = df[mask].copy()
    return df


def atribuir_funis_para_compras(compras_df, leads_bases):
    """
    Para cada compra, identifica quais funis tocaram (cruzando por
    email, telefone, nome+DDD, nome forte) — apenas leads anteriores à compra.

    Args:
        compras_df: DataFrame de compras processado
        leads_bases: dict {funil_name: leads_df}

    Returns:
        Lista de dicts com atribuição por compra.
    """
    resultados = []

    for _, compra in compras_df.iterrows():
        c_email = compra['EMAIL_CLEAN']
        c_phone = compra['PHONE_CLEAN']
        c_nome = compra['NOME_NORM']
        c_ddd = compra['DDD']
        c_dt = compra['DT']

        funis_tocados = []
        match_details = []

        for funil_name, base_df in leads_bases.items():
            if base_df is None or len(base_df) == 0:
                continue

            # Filtrar leads anteriores à compra (se a base tiver data)
            if 'DT' in base_df.columns and pd.notna(c_dt):
                dt_col = base_df['DT']
                # Remove timezone para comparação uniforme
                if hasattr(dt_col.dtype, 'tz') and dt_col.dt.tz is not None:
                    dt_col = dt_col.dt.tz_localize(None)
                c_dt_naive = c_dt.replace(tzinfo=None) if hasattr(c_dt, 'tzinfo') and c_dt.tzinfo else c_dt
                base_eligible = base_df[
                    dt_col.isna() | (dt_col <= c_dt_naive)
                ]
            else:
                base_eligible = base_df

            if len(base_eligible) == 0:
                continue

            tipo_match = None

            # 1. Email
            if c_email and c_email in base_eligible.get('EMAIL_CLEAN', pd.Series([])).values:
                tipo_match = 'email'
            # 2. Telefone
            elif c_phone and c_phone in base_eligible.get('PHONE_CLEAN', pd.Series([])).values:
                tipo_match = 'telefone'
            # 3. Nome forte (sobrenome distintivo)
            elif c_nome:
                for nl in base_eligible['NOME_NORM'].dropna():
                    if nome_forte_match(c_nome, nl):
                        tipo_match = 'nome_forte'
                        break
                # 4. Nome+DDD
                if not tipo_match and c_ddd and c_nome:
                    matching_ddd = base_eligible[base_eligible.get('DDD', pd.Series([])) == c_ddd]
                    for nl in matching_ddd['NOME_NORM'].dropna():
                        # Match parcial: primeiro nome igual + DDD igual
                        nlc = norm_nome(nl)
                        if nlc and c_nome.split()[0] == nlc.split()[0]:
                            tipo_match = 'nome+ddd'
                            break

            if tipo_match:
                funis_tocados.append(funil_name)
                match_details.append({'funil': funil_name, 'tipo': tipo_match})

        resultados.append({
            'nome': compra['USUARIO'],
            'email': c_email,
            'data': compra['DT'].strftime('%d/%m/%Y') if pd.notna(compra['DT']) else '',
            'valor': float(compra['VALOR_NUM']),
            'produto': str(compra.get('PRODUTO', '')).replace('CURSO: ', ''),
            'utm_source': str(compra.get('UTM SOURCE', 'sem UTM')) if pd.notna(compra.get('UTM SOURCE')) else 'sem UTM',
            'funis_tocados': funis_tocados,
            'qtd_funis': len(funis_tocados),
            'match_details': match_details,
        })

    return resultados


def calcular_metricas_funil(funil_name, gasto, leads_df, atribuicoes, receita_indireta=0):
    """Calcula KPIs de um funil: CPL, ROAS, vendas atribuídas, etc."""
    total_leads = len(leads_df) if leads_df is not None else 0
    cpl = gasto / total_leads if total_leads > 0 else 0

    # Vendas em que esse funil foi tocado
    vendas_atribuidas = [
        a for a in atribuicoes if funil_name in a['funis_tocados']
    ]
    receita_atribuida = sum(a['valor'] for a in vendas_atribuidas)
    receita_total = receita_atribuida + receita_indireta
    roas = receita_total / gasto if gasto > 0 else 0
    cpa = gasto / len(vendas_atribuidas) if vendas_atribuidas else 0

    return {
        'funil': funil_name,
        'gasto': gasto,
        'leads_captados': total_leads,
        'cpl': cpl,
        'vendas': len(vendas_atribuidas),
        'receita_atribuida': receita_atribuida,
        'receita_total': receita_total,
        'roas': roas,
        'cpa': cpa,
        'compradoras': vendas_atribuidas,
    }


def filtrar_leads_por_utm(leads_comercial_df, prefix_or_medium, mode='prefix'):
    """
    Filtra leads da planilha comercial por padrão de UTM_SOURCE ou UTM_MEDIUM.

    mode='prefix': busca prefixo em UTM_SOURCE (ex: 'blog_')
    mode='medium': busca match exato em UTM_MEDIUM (ex: 'linktree')
    mode='contains': busca substring em UTM_SOURCE
    """
    if leads_comercial_df is None or len(leads_comercial_df) == 0:
        return pd.DataFrame()

    if mode == 'prefix' and 'UTM_SOURCE' in leads_comercial_df.columns:
        return leads_comercial_df[
            leads_comercial_df['UTM_SOURCE'].astype(str).str.lower().str.startswith(prefix_or_medium.lower())
        ].copy()
    elif mode == 'medium' and 'UTM_MEDIUM' in leads_comercial_df.columns:
        return leads_comercial_df[
            leads_comercial_df['UTM_MEDIUM'].astype(str).str.lower() == prefix_or_medium.lower()
        ].copy()
    elif mode == 'contains' and 'UTM_SOURCE' in leads_comercial_df.columns:
        return leads_comercial_df[
            leads_comercial_df['UTM_SOURCE'].astype(str).str.lower().str.contains(prefix_or_medium.lower(), na=False)
        ].copy()
    return pd.DataFrame()


def cross_funnel_ebook_to_curso(ebook_buyers_df, compras_maiores_df):
    """
    Cruza compradores de ebook (front-end) com compradores de curso maior
    (Concurseiro PRO etc) para identificar upsell.
    """
    cross = []
    for _, eb in ebook_buyers_df.iterrows():
        em = eb['EMAIL_CLEAN']
        ph = eb['PHONE_CLEAN']
        nm = eb['NOME_NORM']

        matched = None
        tipo = None

        if em:
            m = compras_maiores_df[compras_maiores_df['EMAIL_CLEAN'] == em]
            if len(m) > 0:
                matched = m.iloc[0]
                tipo = 'email'
        if matched is None and ph:
            m = compras_maiores_df[compras_maiores_df['PHONE_CLEAN'] == ph]
            if len(m) > 0:
                matched = m.iloc[0]
                tipo = 'telefone'
        if matched is None and nm:
            for _, mc in compras_maiores_df.iterrows():
                if nome_forte_match(nm, mc['NOME_NORM']):
                    matched = mc
                    tipo = 'nome_forte'
                    break

        if matched is not None and matched['DT'] >= eb['DT_VENDA']:
            cross.append({
                'eb_data': eb['DT_VENDA'].strftime('%d/%m/%Y'),
                'eb_nome': str(eb['Nome']),
                'eb_valor': float(eb.get('Preço Total', eb.get('Preço da Oferta', 0))),
                'compra_data': matched['DT'].strftime('%d/%m/%Y'),
                'compra_nome': str(matched['USUARIO']),
                'compra_valor': float(matched['VALOR_NUM']),
                'compra_produto': str(matched.get('PRODUTO', '')),
                'match_tipo': tipo,
                'gap_dias': (matched['DT'] - eb['DT_VENDA']).days,
            })
    return cross


def format_brl(value):
    """Formata valor em real brasileiro."""
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


# ── Parsers para dados vindos direto do Google Sheets ────────────────────────

def parse_compras_sheet(df: "pd.DataFrame", periodo_inicio=None, periodo_fim=None) -> "pd.DataFrame":
    """
    Recebe DataFrame já lido do Google Sheets (via get_vendas) e normaliza
    para o mesmo formato que parse_compras_hotmart retorna.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    df["DT"] = pd.to_datetime(df.get("DT APROVACAO", ""), errors="coerce")

    def _to_num(x):
        s = re.sub(r"[R$\s]", "", str(x)).replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    df["VALOR_NUM"] = df.get("VALOR PAGO", pd.Series(["0"] * len(df))).apply(_to_num)

    # Corrige valores em centavos
    mask = (df["VALOR_NUM"] >= 1000) & (df["VALOR_NUM"] % 1 == 0)
    df.loc[mask, "VALOR_NUM"] = df.loc[mask, "VALOR_NUM"] / 100

    df["EMAIL_CLEAN"] = df.get("EMAIL", pd.Series([""] * len(df))).apply(clean_email)
    df["PHONE_CLEAN"] = df.get("TELEFONE", pd.Series([""] * len(df))).apply(clean_phone)
    df["NOME_NORM"] = df.get("USUARIO", pd.Series([""] * len(df))).apply(norm_nome)
    df["DDD"] = df["PHONE_CLEAN"].apply(extract_ddd_from_phone)

    if "PRODUTO" not in df.columns:
        df["PRODUTO"] = ""
    if "UTM SOURCE" not in df.columns:
        df["UTM SOURCE"] = ""

    df = df[df["VALOR_NUM"] > 0].copy()

    if periodo_inicio and periodo_fim:
        ts_ini = pd.Timestamp(periodo_inicio)
        ts_fim = pd.Timestamp(periodo_fim) + pd.Timedelta(days=1)
        mask = (df["DT"] >= ts_ini) & (df["DT"] < ts_fim)
        df = df[mask].copy()

    return df


def parse_leads_comercial_sheet(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Recebe DataFrame do Sheets (via get_comercial) e normaliza para o formato
    esperado pelas funções de filtro UTM (filtrar_leads_por_utm).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    if "DATA" in df.columns:
        df["DT"] = pd.to_datetime(df["DATA"], errors="coerce", utc=True)
        if hasattr(df["DT"].dtype, "tz") and df["DT"].dt.tz is not None:
            df["DT"] = df["DT"].dt.tz_convert(None)
    else:
        df["DT"] = pd.NaT

    df["EMAIL_CLEAN"] = df.get("E-MAIL / EDITAL", pd.Series([""] * len(df))).apply(clean_email)
    df["PHONE_CLEAN"] = df.get("TELEFONE", pd.Series([""] * len(df))).apply(clean_phone)
    df["NOME_NORM"] = df.get("NOME", pd.Series([""] * len(df))).apply(norm_nome)

    return df


def parse_leads_funil_sheet(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Recebe DataFrame de leads de funil já lido do Sheets e normaliza
    para o mesmo formato que parse_leads_funil retorna.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    name_col = next((c for c in df.columns if c.upper() in ["NOME", "NAME", "NOME_COMPLETO"]), None)
    email_col = next((c for c in df.columns if "EMAIL" in c.upper() or "E-MAIL" in c.upper()), None)
    phone_col = next((c for c in df.columns if any(p in c.upper() for p in ["TELEFONE", "PHONE", "WHATSAPP", "CELULAR"])), None)
    date_col = next((c for c in df.columns if c.upper() in ["DATA", "DATE", "CRIADO_EM", "CREATED_AT"]), None)

    df["NOME_NORM"] = df[name_col].apply(norm_nome) if name_col else ""
    df["EMAIL_CLEAN"] = df[email_col].apply(clean_email) if email_col else ""
    df["PHONE_CLEAN"] = df[phone_col].apply(clean_phone) if phone_col else ""
    df["DDD"] = df["PHONE_CLEAN"].apply(extract_ddd_from_phone)

    if date_col:
        df["DT"] = pd.to_datetime(df[date_col], errors="coerce")

    return df


def parse_ebook_sheet(df: "pd.DataFrame", periodo_inicio=None, periodo_fim=None) -> "pd.DataFrame":
    """
    Recebe DataFrame de compradores do ebook (SHEET_EBOOK) e normaliza.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # Detectar colunas
    date_col = next((c for c in df.columns if "data" in c.lower() or "date" in c.lower() or "cria" in c.lower()), None)
    email_col = next((c for c in df.columns if "email" in c.lower() or "e-mail" in c.lower()), None)
    nome_col = next((c for c in df.columns if c.lower() in ("nome", "name", "usuario")), None)
    phone_col = next((c for c in df.columns if any(p in c.lower() for p in ("tel", "whats", "phone", "celul"))), None)
    valor_col = next((c for c in df.columns if "valor" in c.lower() or "preco" in c.lower() or "price" in c.lower()), None)

    if date_col:
        df["DT_VENDA"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        df["DT_VENDA"] = pd.NaT

    df["EMAIL_CLEAN"] = df[email_col].apply(clean_email) if email_col else ""
    df["NOME_NORM"] = df[nome_col].apply(norm_nome) if nome_col else ""
    df["PHONE_CLEAN"] = df[phone_col].apply(clean_phone) if phone_col else ""
    df["Nome"] = df[nome_col] if nome_col else ""

    if valor_col:
        df["Preço Total"] = pd.to_numeric(
            df[valor_col].astype(str).str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True),
            errors="coerce",
        ).fillna(0)
    else:
        df["Preço Total"] = 0

    if periodo_inicio and periodo_fim and "DT_VENDA" in df.columns:
        ts_ini = pd.Timestamp(periodo_inicio)
        ts_fim = pd.Timestamp(periodo_fim) + pd.Timedelta(days=1)
        mask = (df["DT_VENDA"] >= ts_ini) & (df["DT_VENDA"] < ts_fim)
        df = df[mask].copy()

    return df
