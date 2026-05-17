"""
Dashboard Odon Concursos · Pipeline de Atribuição Multi-Funil
Lê dados diretamente do Google Sheets — sem upload de arquivos.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

from utils.sheets import get_vendas, get_comercial, get_leads_funil, get_ebook, get_crm
from utils.processor import (
    parse_compras_sheet, parse_leads_comercial_sheet,
    parse_leads_funil_sheet, parse_ebook_sheet,
    atribuir_funis_para_compras, calcular_metricas_funil,
    filtrar_leads_por_utm, cross_funnel_ebook_to_curso, format_brl,
)

# ── CONFIG ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Odon Concursos",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main { padding-top: 1rem; }
    [data-testid="stMetric"] {
        background: #f8f9fa; border: 1px solid #e0e0e0;
        border-radius: 12px; padding: 12px 16px;
    }
    [data-testid="stMetricValue"] {
        font-weight: 700; color: #0b1535; font-size: 1.15rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 10px; text-transform: uppercase;
        letter-spacing: 0.7px; color: #6c757d; font-weight: 700;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 3px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] {
        background: #f0f0f0; border-radius: 8px 8px 0 0;
        padding: 6px 11px; font-weight: 600; font-size: 12px;
    }
    .stTabs [aria-selected="true"] { background: #e91e8c !important; color: white !important; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 10px; }
    .funil-row { border-bottom: 1px solid #f0f0f0; padding-bottom: 10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ──────────────────────────────────────────────────────────────────────
st.markdown("# 📊 Dashboard Odon Concursos")
st.markdown("*Pipeline de atribuição multi-funil · Google Sheets · cache 5 min*")

# ── SIDEBAR ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 Investimentos")
    gastos = {}
    with st.expander("**Meta Ads por funil**", expanded=True):
        gastos['ibgp']               = st.number_input("IBGP",          value=2293.35, step=10.0, format='%.2f')
        gastos['imam']               = st.number_input("IMAM",          value=338.61,  step=10.0, format='%.2f')
        gastos['webinario']          = st.number_input("Webinário",     value=1200.20, step=10.0, format='%.2f')
        gastos['ipatinga']           = st.number_input("Ipatinga",      value=1158.38, step=10.0, format='%.2f')
        gastos['petrobras']          = st.number_input("Petrobras",     value=976.25,  step=10.0, format='%.2f')
        gastos['webinario_ipatinga'] = st.number_input("Web. Ipatinga", value=0.0,     step=10.0, format='%.2f')
        gastos['enare']              = st.number_input("ENARE",         value=340.60,  step=10.0, format='%.2f')
        gastos['ebook']              = st.number_input("Ebook",         value=562.55,  step=10.0, format='%.2f')
    with st.expander("**Google Ads**"):
        gastos['google_ads'] = st.number_input("Google Ads", value=871.08, step=10.0, format='%.2f')

    st.markdown("---")
    st.markdown("## 📅 Período")
    c1, c2 = st.columns(2)
    with c1:
        data_inicio = st.date_input("Início", value=date(2026, 5, 1), key='dt_ini')
    with c2:
        data_fim = st.date_input("Fim", value=date.today(), key='dt_fim')
    st.markdown("---")
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── CARREGAMENTO ────────────────────────────────────────────────────────────────
_FUNIS_ATIVOS = ["ibgp", "imam", "webinario", "ipatinga", "petrobras", "webinario_ipatinga"]

with st.spinner("Carregando dados do Google Sheets..."):
    vendas_raw    = get_vendas()
    comercial_raw = get_comercial()
    ebook_raw     = get_ebook()
    crm_raw       = get_crm()
    leads_raw     = {f: get_leads_funil(f) for f in _FUNIS_ATIVOS}

compras         = parse_compras_sheet(vendas_raw, data_inicio, data_fim)
leads_comercial = parse_leads_comercial_sheet(comercial_raw)
bases           = {f: parse_leads_funil_sheet(df) for f, df in leads_raw.items()}
ebook_buyers    = parse_ebook_sheet(ebook_raw, data_inicio, data_fim)

if compras is None or compras.empty:
    st.warning("Nenhuma venda encontrada no período. Ajuste as datas ou verifique a planilha de vendas.")
    st.info(f"Linhas brutas lidas da planilha de vendas: {len(vendas_raw)}")
    st.stop()

atribuicoes = atribuir_funis_para_compras(compras, bases)

# ── KPIs GLOBAIS ────────────────────────────────────────────────────────────────
total_vendas  = len(compras)
receita_total = compras['VALOR_NUM'].sum()
ticket_medio  = receita_total / total_vendas if total_vendas else 0
gasto_total   = sum(gastos.values())
gasto_meta    = sum(v for k, v in gastos.items() if k != 'google_ads')
gasto_google  = gastos.get('google_ads', 0)
roas_global   = receita_total / gasto_total if gasto_total else 0

st.markdown(f"### 📅 {data_inicio.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')}")
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("Vendas",        str(total_vendas))
k2.metric("Receita",       format_brl(receita_total))
k3.metric("Ticket Médio",  format_brl(ticket_medio))
k4.metric("Total Inv.",    format_brl(gasto_total))
k5.metric("Meta Ads",      format_brl(gasto_meta))
k6.metric("Google Ads",    format_brl(gasto_google))
k7.metric("ROAS Global",   f"{roas_global:.2f}x")

# ── helper: calcular ROI de todos os funis ────────────────────────────────────
def _roi_table():
    rows = []
    for funil, gasto in gastos.items():
        if gasto <= 0:
            continue
        if funil == 'google_ads':
            m = compras[compras['UTM SOURCE'].astype(str).str.contains('google', case=False, na=False)]
            receita = m['VALOR_NUM'].sum()
            vendas_n = len(m)
        elif funil == 'enare':
            m = compras[compras['PRODUTO'].astype(str).str.contains('ENARE', case=False, na=False)]
            receita = m['VALOR_NUM'].sum()
            vendas_n = len(m)
        elif funil == 'ebook':
            rec_dir = float(ebook_buyers['Preço Total'].sum()) if ebook_buyers is not None and not ebook_buyers.empty else 0
            cross   = cross_funnel_ebook_to_curso(ebook_buyers, compras) if ebook_buyers is not None and not ebook_buyers.empty else []
            receita  = rec_dir + sum(c['compra_valor'] for c in cross)
            vendas_n = len(ebook_buyers) if ebook_buyers is not None else 0
        else:
            atrib    = [a for a in atribuicoes if funil in a['funis_tocados']]
            receita  = sum(a['valor'] for a in atrib)
            vendas_n = len(atrib)
        roas = receita / gasto if gasto > 0 else 0
        rows.append({
            'Funil':    funil.upper().replace('_', ' '),
            'Tipo':     'Google Ads' if funil == 'google_ads' else 'Meta Ads',
            'Inv.':     gasto,
            'Receita':  receita,
            'Vendas':   vendas_n,
            'ROAS':     f"{roas:.2f}x",
            'ROAS_num': roas,
        })
    return pd.DataFrame(rows).sort_values('ROAS_num', ascending=False).drop('ROAS_num', axis=1)

# ── TABS ────────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Visão Geral",   # 0
    "🎯 Por Funil",     # 1
    "💸 ROI",           # 2
    "📱 Meta Ads",      # 3
    "🔍 Google Ads",    # 4
    "📞 Origem",        # 5
    "🔗 Link na Bio",   # 6
    "📝 Blog",          # 7
    "📋 Compras",       # 8
    "💬 CRM",           # 9
    "🎯 Leads UTM",     # 10
])

# ============ TAB 0 · VISÃO GERAL ============
with tabs[0]:
    st.markdown("### Visão Geral")

    # Investimento Meta vs Google
    ia, ib, ic, id_ = st.columns(4)
    ia.metric("Meta Ads investido",   format_brl(gasto_meta))
    ib.metric("Google Ads investido", format_brl(gasto_google))
    roas_meta = receita_total / gasto_meta if gasto_meta else 0
    ic.metric("ROAS Meta (global)",   f"{roas_meta:.2f}x")
    roas_goog = (compras[compras['UTM SOURCE'].astype(str).str.contains('google', case=False, na=False)]['VALOR_NUM'].sum()) / gasto_google if gasto_google else 0
    id_.metric("ROAS Google Ads",     f"{roas_goog:.2f}x")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Receita por UTM Source")
        utm_rev = compras.groupby('UTM SOURCE')['VALOR_NUM'].agg(['sum', 'count']).reset_index()
        utm_rev.columns = ['UTM Source', 'Receita', 'Vendas']
        utm_rev = utm_rev.sort_values('Receita', ascending=True).fillna('sem UTM')
        fig = px.bar(utm_rev, x='Receita', y='UTM Source', orientation='h',
                     color_discrete_sequence=['#e91e8c'], text='Vendas')
        fig.update_traces(texttemplate='%{text}v', textposition='outside')
        fig.update_layout(height=350, plot_bgcolor='white', margin=dict(l=0, r=30, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Receita por Dia")
        compras['data_dia'] = compras['DT'].dt.date
        vd = compras.groupby('data_dia').agg(receita=('VALOR_NUM', 'sum'), qtd=('VALOR_NUM', 'count')).reset_index()
        fig2 = px.bar(vd, x='data_dia', y='receita', color_discrete_sequence=['#0b1535'], text='qtd')
        fig2.update_traces(texttemplate='%{text}v', textposition='outside')
        fig2.update_layout(height=350, plot_bgcolor='white', margin=dict(l=0, r=10, t=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("#### ROI Detalhado por Funil")
    df_roi = _roi_table()
    st.dataframe(
        df_roi.style.format({'Inv.': lambda x: format_brl(x), 'Receita': lambda x: format_brl(x)}),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    st.markdown("#### Distribuição de Vendas por Funil")
    fd = {}
    for a in atribuicoes:
        k = 'Nenhum' if not a['funis_tocados'] else ('Multi-funil' if len(a['funis_tocados']) > 1 else a['funis_tocados'][0])
        fd.setdefault(k, {'qtd': 0, 'receita': 0})
        fd[k]['qtd'] += 1; fd[k]['receita'] += a['valor']
    df_fd = pd.DataFrame([{'Funil': k, 'Vendas': v['qtd'], 'Receita': v['receita']} for k, v in fd.items()]).sort_values('Receita', ascending=False)
    st.dataframe(df_fd.style.format({'Receita': lambda x: format_brl(x)}), use_container_width=True, hide_index=True)


# ============ TAB 1 · POR FUNIL ============
with tabs[1]:
    st.markdown("### Performance por Funil")
    st.caption("Cruzamento automático por email · telefone · nome. Ebook e ENARE abaixo.")

    _FUNIS_LABELS = {
        'ibgp': 'IBGP', 'imam': 'IMAM', 'webinario': 'Webinário',
        'ipatinga': 'Ipatinga', 'petrobras': 'Petrobras',
        'webinario_ipatinga': 'Web. Ipatinga',
    }

    for funil in _FUNIS_ATIVOS:
        gasto = gastos.get(funil, 0)
        leads_df = bases.get(funil)
        m = calcular_metricas_funil(funil, gasto, leads_df, atribuicoes)
        label = _FUNIS_LABELS.get(funil, funil.upper())

        st.markdown(f"**{label}**")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Gasto",    format_brl(m['gasto']))
        c2.metric("Leads",    str(m['leads_captados']))
        c3.metric("CPL",      format_brl(m['cpl']))
        c4.metric("Vendas",   str(m['vendas']))
        c5.metric("Receita",  format_brl(m['receita_atribuida']))
        c6.metric("ROAS",     f"{m['roas']:.2f}x")

        if m['vendas'] > 0:
            with st.expander(f"Ver {m['vendas']} venda(s) · {label}"):
                df_buy = pd.DataFrame([{
                    'Data': b['data'], 'Nome': b['nome'],
                    'Valor': format_brl(b['valor']), 'Produto': str(b['produto'])[:40],
                    'UTM': b['utm_source'],
                } for b in m['compradoras']])
                st.dataframe(df_buy, use_container_width=True, hide_index=True)
        st.markdown("<div class='funil-row'></div>", unsafe_allow_html=True)

    # ── ENARE ──────────────────────────────────────────────────────────
    st.markdown("**ENARE**")
    gasto_enare = gastos.get('enare', 0)
    enare_match = compras[compras['PRODUTO'].astype(str).str.contains('ENARE', case=False, na=False)]
    rec_enare   = enare_match['VALOR_NUM'].sum()
    roas_enare  = rec_enare / gasto_enare if gasto_enare else 0
    ce1, ce2, ce3, ce4 = st.columns(4)
    ce1.metric("Gasto",   format_brl(gasto_enare))
    ce2.metric("Vendas",  str(len(enare_match)))
    ce3.metric("Receita", format_brl(rec_enare))
    ce4.metric("ROAS",    f"{roas_enare:.2f}x")
    if len(enare_match) > 0:
        with st.expander(f"Ver {len(enare_match)} venda(s) · ENARE"):
            df_enare = enare_match[['DT', 'USUARIO', 'PRODUTO', 'VALOR_NUM', 'UTM SOURCE']].copy()
            df_enare['DT'] = df_enare['DT'].dt.strftime('%d/%m/%Y')
            df_enare['VALOR_NUM'] = df_enare['VALOR_NUM'].apply(format_brl)
            st.dataframe(df_enare, use_container_width=True, hide_index=True)
    st.markdown("<div class='funil-row'></div>", unsafe_allow_html=True)

    # ── EBOOK 500 ────────────────────────────────────────────────────────
    st.markdown("**Ebook 500 Questões**")
    gasto_ebook = gastos.get('ebook', 0)
    if ebook_buyers is not None and not ebook_buyers.empty:
        rec_ebook_dir  = float(ebook_buyers['Preço Total'].sum())
        cross          = cross_funnel_ebook_to_curso(ebook_buyers, compras)
        rec_ebook_cros = sum(c['compra_valor'] for c in cross)
        rec_ebook_tot  = rec_ebook_dir + rec_ebook_cros
        roas_ebook     = rec_ebook_tot / gasto_ebook if gasto_ebook else 0
        eb1, eb2, eb3, eb4, eb5, eb6 = st.columns(6)
        eb1.metric("Gasto",         format_brl(gasto_ebook))
        eb2.metric("Compradores",   str(len(ebook_buyers)))
        eb3.metric("Rec. direta",   format_brl(rec_ebook_dir))
        eb4.metric("Cross-sell",    str(len(cross)))
        eb5.metric("Rec. total",    format_brl(rec_ebook_tot))
        eb6.metric("ROAS",          f"{roas_ebook:.2f}x")
        if cross:
            with st.expander(f"Ver {len(cross)} cross-sell(s) ebook → curso"):
                df_cross = pd.DataFrame([{
                    'Compra ebook': c['eb_data'], 'Nome': c['eb_nome'],
                    'Data curso': c['compra_data'], 'Valor curso': format_brl(c['compra_valor']),
                    'Produto': str(c['compra_produto'])[:40], 'Gap (dias)': c['gap_dias'],
                } for c in cross])
                st.dataframe(df_cross, use_container_width=True, hide_index=True)
    else:
        eb1, eb2 = st.columns(2)
        eb1.metric("Gasto", format_brl(gasto_ebook))
        eb2.metric("Compradores", "0 (sem dados no período)")


# ============ TAB 2 · ROI CONSOLIDADO ============
with tabs[2]:
    st.markdown("### ROI Consolidado")
    df_roi = _roi_table()

    total_inv = df_roi['Inv.'].sum()
    total_rec = df_roi['Receita'].sum()
    roas_g    = total_rec / total_inv if total_inv else 0

    r1, r2, r3 = st.columns(3)
    r1.metric("Total Investido",   format_brl(total_inv))
    r2.metric("Receita Atribuída", format_brl(total_rec))
    r3.metric("ROAS Global",       f"{roas_g:.2f}x", delta=f"{(roas_g-1)*100:.0f}% acima do breakeven")

    st.markdown("---")
    st.dataframe(
        df_roi.style.format({'Inv.': lambda x: format_brl(x), 'Receita': lambda x: format_brl(x)}),
        use_container_width=True, hide_index=True,
    )

    fig_roi = px.bar(
        df_roi.sort_values('Receita', ascending=True),
        x='Receita', y='Funil', orientation='h', color='Tipo',
        color_discrete_map={'Meta Ads': '#e91e8c', 'Google Ads': '#4285F4'},
        text='ROAS',
    )
    fig_roi.update_traces(textposition='outside')
    fig_roi.update_layout(height=420, plot_bgcolor='white', margin=dict(l=0, r=80, t=20, b=20))
    st.plotly_chart(fig_roi, use_container_width=True)


# ============ TAB 3 · META ADS ============
with tabs[3]:
    st.markdown("### 📱 Meta Ads · Performance por Funil")

    _META_FUNIS = ['ibgp', 'imam', 'webinario', 'ipatinga', 'petrobras', 'webinario_ipatinga', 'enare', 'ebook']
    meta_rows = []

    for funil in _META_FUNIS:
        gasto = gastos.get(funil, 0)
        if gasto <= 0:
            continue
        leads_df = bases.get(funil)
        total_leads = len(leads_df) if leads_df is not None else 0
        cpl = gasto / total_leads if total_leads > 0 else 0

        if funil == 'enare':
            m_ = compras[compras['PRODUTO'].astype(str).str.contains('ENARE', case=False, na=False)]
            receita = m_['VALOR_NUM'].sum(); vendas_n = len(m_)
        elif funil == 'ebook':
            rec_d = float(ebook_buyers['Preço Total'].sum()) if ebook_buyers is not None and not ebook_buyers.empty else 0
            cross_ = cross_funnel_ebook_to_curso(ebook_buyers, compras) if ebook_buyers is not None and not ebook_buyers.empty else []
            receita  = rec_d + sum(c['compra_valor'] for c in cross_)
            vendas_n = len(ebook_buyers) if ebook_buyers is not None else 0
        else:
            atrib    = [a for a in atribuicoes if funil in a['funis_tocados']]
            receita  = sum(a['valor'] for a in atrib)
            vendas_n = len(atrib)

        roas = receita / gasto if gasto else 0
        cpa  = gasto / vendas_n if vendas_n else 0
        meta_rows.append({
            'Funil': funil.upper().replace('_', ' '),
            'Inv.': gasto, 'Leads': total_leads, 'CPL': cpl,
            'Vendas': vendas_n, 'Receita': receita, 'CPA': cpa, 'ROAS': roas,
        })

    if meta_rows:
        df_meta = pd.DataFrame(meta_rows)
        tot_meta_inv = df_meta['Inv.'].sum()
        tot_meta_rec = df_meta['Receita'].sum()
        roas_meta_tot = tot_meta_rec / tot_meta_inv if tot_meta_inv else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total investido Meta",  format_brl(tot_meta_inv))
        m2.metric("Receita total Meta",    format_brl(tot_meta_rec))
        m3.metric("ROAS Meta",             f"{roas_meta_tot:.2f}x")
        m4.metric("Funis ativos",          str(len(meta_rows)))

        st.markdown("---")
        col_tbl, col_chart = st.columns([1, 1])
        with col_tbl:
            st.markdown("#### Tabela por funil")
            st.dataframe(
                df_meta.style.format({
                    'Inv.': lambda x: format_brl(x), 'CPL': lambda x: format_brl(x),
                    'Receita': lambda x: format_brl(x), 'CPA': lambda x: format_brl(x),
                    'ROAS': lambda x: f"{x:.2f}x",
                }),
                use_container_width=True, hide_index=True,
            )
        with col_chart:
            st.markdown("#### ROAS por funil")
            fig_m = px.bar(
                df_meta.sort_values('ROAS', ascending=True),
                x='ROAS', y='Funil', orientation='h',
                color_discrete_sequence=['#e91e8c'],
                text=df_meta.sort_values('ROAS', ascending=True)['ROAS'].apply(lambda x: f"{x:.2f}x"),
            )
            fig_m.add_vline(x=1.0, line_dash='dash', line_color='#888', annotation_text='breakeven')
            fig_m.update_traces(textposition='outside')
            fig_m.update_layout(height=380, plot_bgcolor='white', margin=dict(l=0, r=60, t=10, b=10))
            st.plotly_chart(fig_m, use_container_width=True)

        st.markdown("#### Investimento vs Receita")
        df_bar = df_meta.melt(id_vars='Funil', value_vars=['Inv.', 'Receita'], var_name='Tipo', value_name='Valor')
        fig_bar = px.bar(df_bar, x='Funil', y='Valor', color='Tipo', barmode='group',
                         color_discrete_map={'Inv.': '#ccc', 'Receita': '#e91e8c'})
        fig_bar.update_layout(height=350, plot_bgcolor='white', margin=dict(l=0, r=10, t=10, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)


# ============ TAB 4 · GOOGLE ADS ============
with tabs[4]:
    st.markdown("### 🔍 Google Ads")

    gasto_g = gastos.get('google_ads', 0)
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Investimento Google Ads", format_brl(gasto_g))

    google_compras = compras[compras['UTM SOURCE'].astype(str).str.contains('google', case=False, na=False)]
    rec_g  = google_compras['VALOR_NUM'].sum()
    roas_g = rec_g / gasto_g if gasto_g else 0
    g2.metric("Receita atribuída", format_brl(rec_g))
    g3.metric("Vendas atribuídas", str(len(google_compras)))
    g4.metric("ROAS",              f"{roas_g:.2f}x")

    st.markdown("---")

    if len(google_compras) > 0:
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Vendas por UTM Source")
            src_g = google_compras.groupby('UTM SOURCE')['VALOR_NUM'].agg(['sum', 'count']).reset_index()
            src_g.columns = ['UTM Source', 'Receita', 'Vendas']
            fig_gs = px.bar(src_g.sort_values('Receita', ascending=True),
                            x='Receita', y='UTM Source', orientation='h',
                            color_discrete_sequence=['#4285F4'], text='Vendas')
            fig_gs.update_traces(texttemplate='%{text}v', textposition='outside')
            fig_gs.update_layout(height=300, plot_bgcolor='white', margin=dict(l=0, r=30, t=10, b=10))
            st.plotly_chart(fig_gs, use_container_width=True)

        with col_r:
            st.markdown("#### Receita por Produto")
            prod_g = google_compras.groupby('PRODUTO')['VALOR_NUM'].agg(['sum', 'count']).reset_index()
            prod_g.columns = ['Produto', 'Receita', 'Vendas']
            fig_gp = px.pie(prod_g, names='Produto', values='Receita',
                            color_discrete_sequence=px.colors.qualitative.Set2)
            fig_gp.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10))
            st.plotly_chart(fig_gp, use_container_width=True)

        st.markdown("#### Vendas Google Ads no período")
        df_g = google_compras[['DT', 'USUARIO', 'PRODUTO', 'VALOR_NUM', 'UTM SOURCE']].copy()
        df_g['DT'] = df_g['DT'].dt.strftime('%d/%m/%Y %H:%M')
        df_g['VALOR_NUM'] = df_g['VALOR_NUM'].apply(format_brl)
        df_g.columns = ['Data', 'Nome', 'Produto', 'Valor', 'UTM Source']
        st.dataframe(df_g.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma venda atribuída ao Google Ads no período (UTM SOURCE contendo 'google').")
        st.caption(f"UTM Sources presentes: {compras['UTM SOURCE'].dropna().unique().tolist()[:20]}")


# ============ TAB 5 · ORIGEM DAS COMPRAS ============
with tabs[5]:
    st.markdown("### Origem das Compras")
    st.caption("Cada compra rastreada por UTM + funis tocados antes da compra")

    if atribuicoes:
        rows = [{
            'Data':          a['data'],
            'Nome':          a['nome'],
            'Valor':         format_brl(a['valor']),
            'UTM Source':    a['utm_source'],
            'Funis Tocados': ', '.join(a['funis_tocados']) if a['funis_tocados'] else '—',
            'Produto':       str(a['produto'])[:50],
        } for a in atribuicoes]
        df_orig = pd.DataFrame(rows)

        c1, c2 = st.columns(2)
        with c1:
            filtro_funil = st.selectbox(
                "Filtrar por funil",
                options=['Todos'] + sorted(set(f for a in atribuicoes for f in a['funis_tocados'])) + ['Nenhum funil'],
                key='orig_funil',
            )
        with c2:
            filtro_utm = st.text_input("Buscar por UTM (contém)", key='orig_utm')

        df_show = df_orig.copy()
        if filtro_funil != 'Todos':
            if filtro_funil == 'Nenhum funil':
                df_show = df_show[df_show['Funis Tocados'] == '—']
            else:
                df_show = df_show[df_show['Funis Tocados'].str.contains(filtro_funil, na=False)]
        if filtro_utm:
            df_show = df_show[df_show['UTM Source'].str.contains(filtro_utm, case=False, na=False)]

        st.markdown(f"**{len(df_show)} de {len(df_orig)} compras**")
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=500)


# ============ TAB 6 · LINK NA BIO ============
with tabs[6]:
    st.markdown("### 🔗 Link na Bio")

    if leads_comercial is None or leads_comercial.empty:
        st.warning("Planilha Comercial não disponível — verifique SHEET_COMERCIAL no .env.")
    else:
        # Mostrar UTM_MEDIUM disponíveis (para diagnóstico e filtro)
        med_vals = (
            leads_comercial['UTM_MEDIUM'].astype(str).str.strip()
            .replace('', pd.NA).dropna()
        )
        med_unique = sorted(med_vals.unique().tolist())

        st.caption(f"UTM_MEDIUM encontrados na planilha: {med_unique if med_unique else '(nenhum)'}")

        # Filtro de UTM_MEDIUM com todos os valores reais
        opcoes_med = ['Todos'] + med_unique
        default_idx = 0
        if 'linktree' in med_unique:
            default_idx = opcoes_med.index('linktree')
        filtro_med_bio = st.selectbox("Filtrar por UTM_MEDIUM", options=opcoes_med, index=default_idx, key='bio_med')

        if filtro_med_bio == 'Todos':
            bio_leads = leads_comercial.copy()
        else:
            bio_leads = leads_comercial[
                leads_comercial['UTM_MEDIUM'].astype(str).str.strip().str.lower() == filtro_med_bio.lower()
            ].copy()

        # Filtrar por período se DT disponível
        if 'DT' in bio_leads.columns and not bio_leads['DT'].isna().all():
            try:
                bio_periodo = bio_leads[
                    (bio_leads['DT'].dt.date >= data_inicio) & (bio_leads['DT'].dt.date <= data_fim)
                ]
            except Exception:
                bio_periodo = bio_leads
        else:
            bio_periodo = bio_leads

        c1, c2, c3 = st.columns(3)
        c1.metric("Leads no período",  str(len(bio_periodo)))
        c2.metric("Leads histórico",   str(len(bio_leads)))

        # Cruzar com compras por email
        bio_vendas = 0; bio_receita = 0.0
        if 'EMAIL_CLEAN' in bio_leads.columns:
            bio_emails = set(bio_leads['EMAIL_CLEAN'].dropna())
            for a in atribuicoes:
                if a['email'] and a['email'] in bio_emails:
                    bio_vendas += 1; bio_receita += a['valor']
        c3.metric("Vendas atribuídas", str(bio_vendas), delta=format_brl(bio_receita) if bio_receita else None)

        if len(bio_periodo) > 0:
            st.markdown("#### Leads do período")
            show_c = [c for c in ['NOME', 'E-MAIL / EDITAL', 'TELEFONE', 'UTM_SOURCE', 'UTM_MEDIUM', 'UTM_CAMPAIGN', 'DATA'] if c in bio_periodo.columns]
            st.dataframe(bio_periodo[show_c], use_container_width=True, hide_index=True, height=400)
        else:
            st.info("Nenhum lead encontrado com esse filtro no período selecionado.")
            if len(bio_leads) > 0:
                st.markdown("#### Todos os leads com esse UTM_MEDIUM (independente do período)")
                show_c = [c for c in ['NOME', 'E-MAIL / EDITAL', 'TELEFONE', 'UTM_SOURCE', 'UTM_MEDIUM', 'DATA'] if c in bio_leads.columns]
                st.dataframe(bio_leads[show_c].head(100), use_container_width=True, hide_index=True)


# ============ TAB 7 · BLOG ============
with tabs[7]:
    st.markdown("### 📝 Blog")
    st.caption("Leads capturados via posts do blog (UTM_SOURCE começa com `blog_`)")

    if leads_comercial is None or leads_comercial.empty:
        st.warning("Planilha Comercial não disponível — verifique SHEET_COMERCIAL no .env.")
    else:
        blog_leads = filtrar_leads_por_utm(leads_comercial, 'blog_', mode='prefix')

        if 'DT' in blog_leads.columns and not blog_leads['DT'].isna().all():
            try:
                blog_periodo = blog_leads[
                    (blog_leads['DT'].dt.date >= data_inicio) & (blog_leads['DT'].dt.date <= data_fim)
                ]
            except Exception:
                blog_periodo = blog_leads
        else:
            blog_periodo = blog_leads

        blog_vendas = 0; blog_receita = 0.0; blog_compradores = []
        if 'EMAIL_CLEAN' in blog_leads.columns:
            blog_emails = set(blog_leads['EMAIL_CLEAN'].dropna())
            for a in atribuicoes:
                if a['email'] and a['email'] in blog_emails:
                    blog_vendas += 1; blog_receita += a['valor']
                    blog_compradores.append({'nome': a['nome'], 'data': a['data'], 'valor': a['valor']})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Leads no período",  str(len(blog_periodo)))
        c2.metric("Leads (total)",     str(len(blog_leads)))
        c3.metric("Vendas atribuídas", str(blog_vendas))
        c4.metric("Receita atribuída", format_brl(blog_receita))

        if len(blog_periodo) > 0:
            st.markdown("#### Top posts (por leads gerados)")
            top_posts = blog_periodo['UTM_SOURCE'].value_counts().head(15).reset_index()
            top_posts.columns = ['Post (UTM)', 'Leads']
            st.dataframe(top_posts, use_container_width=True, hide_index=True)

        if blog_compradores:
            st.markdown("#### Compradores do blog")
            df_bc = pd.DataFrame([{'Data': c['data'], 'Nome': c['nome'], 'Valor': format_brl(c['valor'])} for c in blog_compradores])
            st.dataframe(df_bc, use_container_width=True, hide_index=True)


# ============ TAB 8 · TODAS AS COMPRAS ============
with tabs[8]:
    st.markdown("### Todas as Compras do Período")
    cols_show = [c for c in ['DT', 'USUARIO', 'PRODUTO', 'VALOR_NUM', 'UTM SOURCE', 'EMAIL'] if c in compras.columns]
    df_all = compras[cols_show].copy().sort_values('DT', ascending=False)
    df_all['DT'] = df_all['DT'].dt.strftime('%d/%m/%Y %H:%M')
    df_all['VALOR_NUM'] = df_all['VALOR_NUM'].apply(format_brl)
    df_all.columns = ['Data', 'Nome', 'Produto', 'Valor', 'UTM Source', 'Email'][:len(cols_show)]
    st.dataframe(df_all, use_container_width=True, hide_index=True, height=600)
    csv = df_all.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar CSV", csv,
                       file_name=f"compras_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.csv",
                       mime='text/csv')


# ============ TAB 9 · CRM COMERCIAL ============
with tabs[9]:
    st.markdown("### 💬 CRM Comercial (WhatsApp)")

    if crm_raw is None or crm_raw.empty:
        st.warning("Planilha CRM não disponível — verifique SHEET_CRM no .env.")
    else:
        df_crm = crm_raw.copy()

        # Detectar colunas com dados reais
        def _has_data(col):
            return df_crm[col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).notna().any()

        cols_with_data = [c for c in df_crm.columns if not c.startswith("_col_") and _has_data(c)]
        st.caption(f"Planilha: {len(df_crm)} linhas · colunas detectadas: {cols_with_data}")

        ALL_STD = ["NOME", "TELEFONE", "EMAIL", "DATA", "STATUS", "RESPONDEU",
                   "RESULTADO", "MOTIVO", "FUNIL", "EDITAL", "ORIGEM", "MENSAGEM"]
        display_cols = [c for c in ALL_STD if c in cols_with_data] or cols_with_data

        total_rows  = len(df_crm)
        status_col  = "STATUS"    if "STATUS"    in cols_with_data else None
        result_col  = "RESULTADO" if "RESULTADO" in cols_with_data else None
        motivo_col  = "MOTIVO"    if "MOTIVO"    in cols_with_data else None
        funil_col   = "FUNIL"     if "FUNIL"     in cols_with_data else None
        edital_col  = "EDITAL"    if "EDITAL"    in cols_with_data else None
        origem_col  = "ORIGEM"    if "ORIGEM"    in cols_with_data else None
        data_col    = "DATA"      if "DATA"       in cols_with_data else None

        # ── Classificação Ganho / Perda ──────────────────────────────────────
        _GANHO = {"ganho", "ganhou", "fechou", "converteu", "sim", "yes", "venda", "vendeu", "fechado", "sucesso"}
        _PERDA = {"perda", "perdeu", "perdido", "não", "nao", "no", "negativa", "recusou", "desistiu", "cancelou", "sem interesse"}

        def _classif(v):
            vl = str(v).strip().lower()
            if not vl or vl == 'nan':
                return "🔄 Em andamento"
            if vl in _GANHO or any(vl.startswith(p) for p in ("ganho", "fechou", "vendeu", "conver")):
                return "✅ Ganho"
            if vl in _PERDA or any(vl.startswith(p) for p in ("perd", "não", "nao", "cancel", "desist")):
                return "❌ Perda"
            return "🔄 Em andamento"

        src_classif = result_col or status_col
        df_crm["_CLASSIF"] = df_crm[src_classif].apply(_classif) if src_classif else "🔄 Em andamento"

        if src_classif:
            raw_vals = df_crm[src_classif].astype(str).str.strip().unique().tolist()
            st.caption(f"Valores em '{src_classif}' usados para classificação: {raw_vals[:20]}")

        cc = df_crm["_CLASSIF"].value_counts()
        ganhos    = int(cc.get("✅ Ganho", 0))
        perdas    = int(cc.get("❌ Perda", 0))
        andamento = int(cc.get("🔄 Em andamento", 0))
        tx_conv   = ganhos / (ganhos + perdas) * 100 if (ganhos + perdas) > 0 else 0

        # ── KPIs ─────────────────────────────────────────────────────────────
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total contatos",    str(total_rows))
        k2.metric("✅ Ganhos",          str(ganhos))
        k3.metric("❌ Perdas",          str(perdas))
        k4.metric("🔄 Em andamento",   str(andamento))
        k5.metric("Taxa de conversão", f"{tx_conv:.1f}%")

        st.markdown("---")

        # ── Seção 1: Resultado geral ──────────────────────────────────────────
        try:
            cc_vals = df_crm["_CLASSIF"].value_counts()
            df_cc = pd.DataFrame({"Resultado": cc_vals.index.tolist(), "Qtd": cc_vals.values.tolist()})
            fig_pie = px.pie(
                df_cc, names="Resultado", values="Qtd",
                color="Resultado",
                color_discrete_map={"✅ Ganho": "#4caf50", "❌ Perda": "#f44336", "🔄 Em andamento": "#ff9800"},
            )
            fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10))
            st.markdown("#### Resultado geral")
            st.plotly_chart(fig_pie, use_container_width=True, key="crm_pie")
        except Exception as _e:
            st.error(f"Erro no gráfico de resultado: {_e}")

        # ── Seção 2: Motivos ──────────────────────────────────────────────────
        if motivo_col:
            try:
                mc1, mc2 = st.columns(2)
                with mc1:
                    st.markdown("#### Motivos de Perda")
                    if perdas > 0:
                        df_p = df_crm[df_crm["_CLASSIF"] == "❌ Perda"]
                        s_p = df_p[motivo_col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).dropna().value_counts().head(10)
                        if not s_p.empty:
                            df_mp = pd.DataFrame({"Motivo": s_p.index.tolist(), "Qtd": s_p.values.tolist()})
                            fig_mp = px.bar(df_mp, x='Qtd', y='Motivo', orientation='h', color_discrete_sequence=["#f44336"])
                            fig_mp.update_layout(height=max(200, len(df_mp)*34), plot_bgcolor='white', margin=dict(l=0,r=20,t=10,b=10))
                            st.plotly_chart(fig_mp, use_container_width=True, key="crm_mot_perda")
                        else:
                            st.info("Sem motivos registrados.")
                    else:
                        st.info("Nenhuma perda registrada.")
                with mc2:
                    st.markdown("#### Motivos de Ganho")
                    if ganhos > 0:
                        df_g = df_crm[df_crm["_CLASSIF"] == "✅ Ganho"]
                        s_g = df_g[motivo_col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).dropna().value_counts().head(10)
                        if not s_g.empty:
                            df_mg = pd.DataFrame({"Motivo": s_g.index.tolist(), "Qtd": s_g.values.tolist()})
                            fig_mg = px.bar(df_mg, x='Qtd', y='Motivo', orientation='h', color_discrete_sequence=["#4caf50"])
                            fig_mg.update_layout(height=max(200, len(df_mg)*34), plot_bgcolor='white', margin=dict(l=0,r=20,t=10,b=10))
                            st.plotly_chart(fig_mg, use_container_width=True, key="crm_mot_ganho")
                        else:
                            st.info("Sem motivos registrados.")
                    else:
                        st.info("Nenhum ganho registrado.")
            except Exception as _e:
                st.error(f"Erro nos motivos: {_e}")

        st.markdown("---")

        # ── Seção 3: Gráfico Diário ───────────────────────────────────────────
        st.markdown("#### Evolução Diária — Leads, Conversões e Taxa")
        try:
            if data_col:
                df_crm["_DATA_DT"] = pd.to_datetime(df_crm[data_col], errors="coerce", dayfirst=True)
                df_valid = df_crm[df_crm["_DATA_DT"].notna()].copy()
                df_valid["_DIA"] = df_valid["_DATA_DT"].dt.date

                if len(df_valid) > 0:
                    agg = df_valid.groupby("_DIA").agg(
                        leads=("_DIA", "count"),
                        ganhos=("_CLASSIF", lambda x: (x == "✅ Ganho").sum()),
                    ).reset_index()
                    agg["taxa"] = (agg["ganhos"] / agg["leads"] * 100).round(1)

                    fig_daily = go.Figure()
                    fig_daily.add_trace(go.Bar(x=agg["_DIA"], y=agg["leads"], name="Leads", marker_color="#0b1535", opacity=0.75))
                    fig_daily.add_trace(go.Bar(x=agg["_DIA"], y=agg["ganhos"], name="Conversões", marker_color="#4caf50"))
                    fig_daily.add_trace(go.Scatter(
                        x=agg["_DIA"], y=agg["taxa"], name="Taxa Conv. %",
                        mode="lines+markers", yaxis="y2",
                        line=dict(color="#e91e8c", width=2), marker=dict(size=6),
                    ))
                    fig_daily.update_layout(
                        barmode="group", height=380, plot_bgcolor="white",
                        legend=dict(orientation="h", y=1.08),
                        margin=dict(l=0, r=60, t=30, b=20),
                        yaxis=dict(title="Quantidade", gridcolor="#f0f0f0"),
                        yaxis2=dict(title="Taxa %", overlaying="y", side="right", range=[0, 105], ticksuffix="%"),
                    )
                    st.plotly_chart(fig_daily, use_container_width=True, key="crm_daily")
                else:
                    st.info("Nenhum registro com data válida para o gráfico diário.")
            else:
                st.info("Coluna de data não detectada na planilha CRM.")
        except Exception as _e:
            st.error(f"Erro no gráfico diário: {_e}")

        st.markdown("---")

        # ── Seção 4: Por Funil ────────────────────────────────────────────────
        funil_col_eff = funil_col or status_col
        if funil_col_eff:
            try:
                st.markdown(f"#### Por Funil  *(coluna: {funil_col_eff})*")
                grp = df_crm.groupby(funil_col_eff, dropna=True).agg(
                    Leads=(funil_col_eff, "count"),
                    Ganhos=("_CLASSIF", lambda x: (x == "✅ Ganho").sum()),
                    Perdas=("_CLASSIF", lambda x: (x == "❌ Perda").sum()),
                    Em_andamento=("_CLASSIF", lambda x: (x == "🔄 Em andamento").sum()),
                ).reset_index().rename(columns={funil_col_eff: "Funil"})
                grp = grp[grp["Funil"].astype(str).str.strip().ne("")]
                grp["Taxa %"] = (grp["Ganhos"] / (grp["Ganhos"] + grp["Perdas"]) * 100).fillna(0).round(1)
                grp = grp.sort_values("Leads", ascending=False).reset_index(drop=True)

                grp_disp = grp.copy()
                grp_disp["Taxa %"] = grp_disp["Taxa %"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(grp_disp, use_container_width=True, hide_index=True)

                fig_f = go.Figure()
                fig_f.add_trace(go.Bar(x=grp["Funil"], y=grp["Leads"],  name="Leads",  marker_color="#0b1535", opacity=0.75))
                fig_f.add_trace(go.Bar(x=grp["Funil"], y=grp["Ganhos"], name="Ganhos", marker_color="#4caf50"))
                fig_f.add_trace(go.Bar(x=grp["Funil"], y=grp["Perdas"], name="Perdas", marker_color="#f44336"))
                fig_f.add_trace(go.Scatter(
                    x=grp["Funil"], y=grp["Taxa %"], name="Taxa %",
                    mode="lines+markers", yaxis="y2",
                    line=dict(color="#e91e8c", width=2), marker=dict(size=7),
                ))
                fig_f.update_layout(
                    barmode="group", height=360, plot_bgcolor="white",
                    legend=dict(orientation="h", y=1.08),
                    margin=dict(l=0, r=60, t=30, b=20),
                    yaxis=dict(title="Quantidade", gridcolor="#f0f0f0"),
                    yaxis2=dict(title="Taxa %", overlaying="y", side="right", range=[0, 105], ticksuffix="%"),
                )
                st.plotly_chart(fig_f, use_container_width=True, key="crm_por_funil")
            except Exception as _e:
                st.error(f"Erro na seção Por Funil: {_e}")
            st.markdown("---")

        # ── Seção 5: Origem dos Leads ─────────────────────────────────────────
        if origem_col:
            try:
                st.markdown("#### Origem dos Leads")
                orig_counts = (
                    df_crm[origem_col].astype(str).str.strip()
                    .replace({'': pd.NA, 'nan': pd.NA}).dropna()
                    .value_counts().head(20)
                )
                if len(orig_counts) > 0:
                    df_orig = pd.DataFrame({"Origem": orig_counts.index.tolist(), "Leads": orig_counts.values.tolist()})
                    fig_o = px.bar(df_orig, x='Leads', y='Origem', orientation='h', color_discrete_sequence=['#e91e8c'])
                    fig_o.update_layout(height=max(200, len(df_orig)*32), plot_bgcolor='white', margin=dict(l=0,r=20,t=10,b=10))
                    st.plotly_chart(fig_o, use_container_width=True, key="crm_origem")

                    conv_orig = df_crm[df_crm[origem_col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).notna()].groupby(origem_col, dropna=True).agg(
                        Leads=(origem_col, "count"),
                        Ganhos=("_CLASSIF", lambda x: (x == "✅ Ganho").sum()),
                    ).reset_index().rename(columns={origem_col: "Origem"}).sort_values("Leads", ascending=False)
                    conv_orig["Taxa %"] = (conv_orig["Ganhos"] / conv_orig["Leads"] * 100).round(1).apply(lambda x: f"{x:.1f}%")
                    st.dataframe(conv_orig, use_container_width=True, hide_index=True)
                st.markdown("---")
            except Exception as _e:
                st.error(f"Erro na seção Origem: {_e}")

        # ── Seção 6: Editais de Interesse ─────────────────────────────────────
        if edital_col:
            try:
                st.markdown("#### Editais de Interesse")
                ed_counts = (
                    df_crm[edital_col].astype(str).str.strip()
                    .replace({'': pd.NA, 'nan': pd.NA}).dropna()
                    .value_counts().head(20)
                )
                if len(ed_counts) > 0:
                    df_ed = pd.DataFrame({"Edital": ed_counts.index.tolist(), "Leads": ed_counts.values.tolist()})
                    fig_ed = px.bar(df_ed, x='Leads', y='Edital', orientation='h', color_discrete_sequence=['#0b1535'])
                    fig_ed.update_layout(height=max(200, len(df_ed)*34), plot_bgcolor='white', margin=dict(l=0,r=20,t=10,b=10))
                    st.plotly_chart(fig_ed, use_container_width=True, key="crm_editais")

                    conv_ed = df_crm[df_crm[edital_col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).notna()].groupby(edital_col, dropna=True).agg(
                        Leads=(edital_col, "count"),
                        Ganhos=("_CLASSIF", lambda x: (x == "✅ Ganho").sum()),
                        Perdas=("_CLASSIF", lambda x: (x == "❌ Perda").sum()),
                    ).reset_index().rename(columns={edital_col: "Edital"}).sort_values("Leads", ascending=False)
                    conv_ed["Taxa %"] = (conv_ed["Ganhos"] / conv_ed["Leads"] * 100).round(1).apply(lambda x: f"{x:.1f}%")
                    st.dataframe(conv_ed, use_container_width=True, hide_index=True)
                st.markdown("---")
            except Exception as _e:
                st.error(f"Erro na seção Editais: {_e}")

        # ── Pipeline por Status ───────────────────────────────────────────────
        if status_col:
            try:
                sv = df_crm[status_col].astype(str).str.strip()
                status_counts = sv[sv.ne("") & sv.ne("STATUS")].value_counts()
                if len(status_counts) > 0:
                    st.markdown("#### Pipeline por Status")
                    df_sc = pd.DataFrame({"Status": status_counts.index.tolist(), "Qtd": status_counts.values.tolist()})
                    fig_st = px.bar(df_sc, x='Qtd', y='Status', orientation='h', color_discrete_sequence=['#e91e8c'])
                    fig_st.update_layout(height=max(200, len(df_sc)*35), plot_bgcolor='white', margin=dict(l=0,r=20,t=10,b=10))
                    st.plotly_chart(fig_st, use_container_width=True, key="crm_status")
                    st.markdown("---")
            except Exception as _e:
                st.error(f"Erro no pipeline por status: {_e}")

        # ── Filtros + Tabela ──────────────────────────────────────────────────
        filtro_classif = st.selectbox("Resultado",
            ["Todos", "✅ Ganho", "❌ Perda", "🔄 Em andamento"], key='crm_classif')

        funis_uniq = sorted(df_crm[funil_col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).dropna().unique().tolist()) if funil_col else []
        filtro_funil_crm = st.selectbox("Funil", ['Todos'] + funis_uniq, key='crm_funil') if funis_uniq else 'Todos'

        editais_uniq = sorted(df_crm[edital_col].astype(str).str.strip().replace({'': pd.NA, 'nan': pd.NA}).dropna().unique().tolist()) if edital_col else []
        filtro_edital = st.selectbox("Edital", ['Todos'] + editais_uniq, key='crm_edital') if editais_uniq else 'Todos'

        filtro_busca = st.text_input("Buscar (nome, telefone...)", key='crm_busca')

        df_show_crm = df_crm.copy()
        if filtro_classif != "Todos":
            df_show_crm = df_show_crm[df_show_crm["_CLASSIF"] == filtro_classif]
        if filtro_funil_crm != 'Todos' and funil_col:
            df_show_crm = df_show_crm[df_show_crm[funil_col].astype(str).str.strip() == filtro_funil_crm]
        if filtro_edital != 'Todos' and edital_col:
            df_show_crm = df_show_crm[df_show_crm[edital_col].astype(str).str.strip() == filtro_edital]
        if filtro_busca:
            mask = pd.Series(False, index=df_show_crm.index)
            for col in display_cols:
                mask |= df_show_crm[col].astype(str).str.contains(filtro_busca, case=False, na=False)
            df_show_crm = df_show_crm[mask]

        tbl_cols = ["_CLASSIF"] + [c for c in display_cols if c != "_CLASSIF" and c in df_show_crm.columns]
        st.markdown(f"**{len(df_show_crm)} de {total_rows} contatos**")
        st.dataframe(
            df_show_crm[tbl_cols].rename(columns={"_CLASSIF": "Resultado"}),
            use_container_width=True, hide_index=True, height=500,
        )

        csv_crm = df_show_crm[tbl_cols].rename(columns={"_CLASSIF": "Resultado"}).to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar CRM CSV", csv_crm,
                           file_name=f"crm_{date.today().strftime('%Y%m%d')}.csv",
                           mime='text/csv', key='dl_crm')


# ============ TAB 10 · LEADS UTM ============
with tabs[10]:
    st.markdown("### 🎯 Leads Formulário UTM")
    st.caption("Leads capturados via formulário com rastreamento UTM (planilha comercial)")

    if leads_comercial is None or leads_comercial.empty:
        st.warning("Planilha Comercial não disponível — verifique SHEET_COMERCIAL no .env.")
    else:
        df_utm = leads_comercial.copy()

        if 'DT' in df_utm.columns and not df_utm['DT'].isna().all():
            try:
                df_periodo = df_utm[
                    (df_utm['DT'].dt.date >= data_inicio) & (df_utm['DT'].dt.date <= data_fim)
                ]
            except Exception:
                df_periodo = df_utm
        else:
            df_periodo = df_utm

        src_counts = (
            df_periodo['UTM_SOURCE'].astype(str).str.strip()
            .replace({'': pd.NA, 'UTM_SOURCE': pd.NA}).dropna()
            .value_counts()
        )
        med_counts = (
            df_periodo['UTM_MEDIUM'].astype(str).str.strip()
            .replace({'': pd.NA, 'UTM_MEDIUM': pd.NA}).dropna()
            .value_counts()
        )

        u1, u2, u3, u4 = st.columns(4)
        u1.metric("Leads no período",  str(len(df_periodo)))
        u2.metric("Leads histórico",   str(len(df_utm)))
        u3.metric("Top source",        src_counts.index[0] if len(src_counts) else '—')
        u4.metric("Top medium",        med_counts.index[0] if len(med_counts) else '—')

        st.markdown("---")
        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("#### Leads por UTM Source")
            if len(src_counts) > 0:
                fig_s = px.bar(src_counts.head(15).reset_index(),
                               x='count', y='UTM_SOURCE', orientation='h',
                               color_discrete_sequence=['#e91e8c'],
                               labels={'count': 'Leads', 'UTM_SOURCE': ''})
                fig_s.update_layout(height=350, plot_bgcolor='white', margin=dict(l=0, r=20, t=10, b=10))
                st.plotly_chart(fig_s, use_container_width=True)

        with col_r:
            st.markdown("#### Leads por UTM Medium")
            if len(med_counts) > 0:
                fig_m = px.pie(med_counts.reset_index(), names='UTM_MEDIUM', values='count',
                               color_discrete_sequence=px.colors.qualitative.Set2)
                fig_m.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=10))
                st.plotly_chart(fig_m, use_container_width=True)

        camp_counts = (
            df_periodo['UTM_CAMPAIGN'].astype(str).str.strip()
            .replace({'': pd.NA, 'UTM_CAMPAIGN': pd.NA}).dropna()
            .value_counts().head(10)
        )
        if len(camp_counts) > 0:
            st.markdown("#### Top 10 Campanhas")
            st.dataframe(
                camp_counts.reset_index().rename(columns={'UTM_CAMPAIGN': 'Campanha', 'count': 'Leads'}),
                use_container_width=True, hide_index=True,
            )

        st.markdown("---")
        st.markdown("#### Tabela de Leads")
        lf1, lf2, lf3 = st.columns(3)
        with lf1:
            filtro_src = st.selectbox("UTM Source", ['Todos'] + sorted(df_utm['UTM_SOURCE'].astype(str).str.strip().unique()), key='utm_src')
        with lf2:
            filtro_med = st.selectbox("UTM Medium", ['Todos'] + sorted(df_utm['UTM_MEDIUM'].astype(str).str.strip().unique()), key='utm_med')
        with lf3:
            filtro_nome = st.text_input("Buscar nome/email", key='utm_nome')

        df_show_utm = df_periodo.copy()
        if filtro_src != 'Todos':
            df_show_utm = df_show_utm[df_show_utm['UTM_SOURCE'].astype(str).str.strip() == filtro_src]
        if filtro_med != 'Todos':
            df_show_utm = df_show_utm[df_show_utm['UTM_MEDIUM'].astype(str).str.strip() == filtro_med]
        if filtro_nome:
            mask = (
                df_show_utm['NOME'].astype(str).str.contains(filtro_nome, case=False, na=False) |
                df_show_utm['E-MAIL / EDITAL'].astype(str).str.contains(filtro_nome, case=False, na=False)
            )
            df_show_utm = df_show_utm[mask]

        show_c = [c for c in ['NOME', 'E-MAIL / EDITAL', 'TELEFONE', 'UTM_SOURCE', 'UTM_MEDIUM', 'UTM_CAMPAIGN', 'DATA'] if c in df_show_utm.columns]
        st.markdown(f"**{len(df_show_utm)} leads**")
        st.dataframe(df_show_utm[show_c], use_container_width=True, hide_index=True, height=500)

        csv_utm = df_show_utm[show_c].to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Leads UTM CSV", csv_utm,
                           file_name=f"leads_utm_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.csv",
                           mime='text/csv', key='dl_utm')


# ── FOOTER ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"Dados via Google Sheets · Cache 5 min · {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
