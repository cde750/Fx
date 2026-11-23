import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from core.contracts import CONTRACTS, CURRENCIES
from core.data import DEFAULT_PRICES, fetch_prices
from core.engine import (build_combos, pareto, best_combo, theoretical_ratio,
                         cross, pnl, pip_value, usd_per)

st.set_page_config(page_title="FX Futures Crosses", page_icon="💱",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------- CSS responsive (iPhone / iPad mini / iPad Air / Mac) ----------
st.markdown("""
<style>
#MainMenu, footer {visibility:hidden;}
.block-container {padding-top:1.2rem; padding-bottom:2rem; max-width:1400px;}
h1 {font-size:1.6rem !important; letter-spacing:-0.5px;}
div[data-testid="stMetric"]{
  background:#111A2E; border:1px solid #1F2A44; border-radius:14px;
  padding:12px 14px;
}
div[data-testid="stMetricValue"]{font-size:1.35rem; font-variant-numeric:tabular-nums;}
.tag{display:inline-block;padding:2px 10px;border-radius:999px;
     background:#1E3A8A;color:#DBEAFE;font-size:.78rem;margin-right:6px;}
.legs{font-family:ui-monospace,Menlo,monospace;font-size:1.05rem;
      background:#0F172A;border-radius:10px;padding:10px 14px;border:1px solid #1F2A44;}
/* iPhone */
@media (max-width: 640px){
  .block-container{padding-left:.6rem; padding-right:.6rem;}
  h1{font-size:1.25rem !important;}
  div[data-testid="stMetricValue"]{font-size:1.1rem;}
  button[data-baseweb="tab"]{padding:6px 8px; font-size:.85rem;}
}
/* iPad mini / iPad Air portrait */
@media (min-width: 641px) and (max-width: 1100px){
  .block-container{padding-left:1.2rem; padding-right:1.2rem;}
}
</style>
<meta name="apple-mobile-web-app-capable" content="yes">
""", unsafe_allow_html=True)

# ---------- Prix ----------
@st.cache_data(ttl=120, show_spinner=False)
def cached_prices():
    return fetch_prices()

if "prices" not in st.session_state:
    live, src = cached_prices()
    st.session_state.prices = live or DEFAULT_PRICES.copy()
    st.session_state.src = src
    st.session_state.ts = datetime.now().strftime("%H:%M:%S")

P = st.session_state.prices

def fmt_rate(x, quote):
    return f"{x:,.3f}" if quote == "JPY" else f"{x:,.5f}"

def legs_label(c):
    parts = []
    for ccy, n in ((c.base, c.n_base), (c.quote, c.n_quote)):
        if n:
            parts.append(f"{'ACHAT' if n > 0 else 'VENTE'} {abs(n)} {CONTRACTS[ccy].code}")
    return "  |  ".join(parts)

def combos_df(combos, base, quote):
    return pd.DataFrame([{
        "Combinaison": legs_label(c),
        "Lots total": c.total_lots,
        f"Nominal {base}": c.base_notional,
        f"Nominal {quote}": c.quote_notional,
        "Erreur %": c.error_pct * 100,
        "Résiduel USD": c.residual_usd,
    } for c in combos])

def expo_label(x: float) -> str:
    if abs(x) < 1:
        return "Neutre"
    return f"{'Long' if x > 0 else 'Short'} USD {abs(x):,.0f} $"DF_FMT = {"Erreur %": st.column_config.NumberColumn(format="%.3f %%"),
          "Résiduel USD": st.column_config.NumberColumn(format="%,.0f $")}

# ---------- En-tête ----------
st.markdown("# 💱 FX Futures Cross Builder")
st.markdown(f"<span class='tag'>{st.session_state.src}</span>"
            f"<span class='tag'>MAJ {st.session_state.ts}</span>", unsafe_allow_html=True)

tab_build, tab_pnl, tab_matrix, tab_prices = st.tabs(
    ["🧮 Constructeur", "💰 P&L", "🌐 Vue devise", "⚙️ Prix"])

# =================== CONSTRUCTEUR ===================
with tab_build:
    c1, c2, c3, c4 = st.columns(4)
    base = c1.selectbox("Devise de base", CURRENCIES, index=1)
    quote = c2.selectbox("Devise de cotation", CURRENCIES, index=3)
    sens = c3.selectbox("Sens", ["Achat", "Vente"])
    max_lots = c4.slider("Lots max (base)", 1, 200, 50)
    direction = 1 if sens == "Achat" else -1

    if base == quote:
        st.warning("Choisissez deux devises différentes.")
    else:
        combos = build_combos(base, quote, P, max_lots, direction)
        best = best_combo(combos)
        x = cross(base, quote, P)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"{base}/{quote} synthétique", fmt_rate(x, quote))
        if "USD" in (base, quote):
            m2.metric("Ratio théorique", "1 jambe")
        else:
            m2.metric("Ratio théorique", f"{theoretical_ratio(base, quote, P):.4f}")
        m3.metric("Meilleure erreur", f"{best.error_pct*100:.3f} %")
        m4.metric("Valeur du pip (USD)", f"{pip_value(best, P):,.2f} $")

        st.markdown(f"**Meilleur ratio (≤ {max_lots} lots)**")
        st.markdown(f"<div class='legs'>{legs_label(best)}</div>", unsafe_allow_html=True)

        st.markdown("#### Ratios optimaux par taille")
        st.caption("Chaque ligne améliore l'erreur par rapport aux combinaisons plus petites.")
        front = pareto(combos)
        st.dataframe(combos_df(front, base, quote), hide_index=True,
                     width="stretch", column_config=DF_FMT)

        with st.expander("Toutes les combinaisons"):
            st.dataframe(combos_df(combos, base, quote), hide_index=True,
                         width="stretch", column_config=DF_FMT)

        # Sélection pour le P&L
        labels = [legs_label(c) for c in front]
        pick = st.selectbox("Combinaison à analyser dans l'onglet P&L",
                            labels, index=len(labels) - 1)
        st.session_state.sel = front[labels.index(pick)]

# =================== P&L ===================
with tab_pnl:
    sel = st.session_state.get("sel")
    if sel is None:
        st.info("Choisissez d'abord une combinaison dans le Constructeur.")
    else:
        st.markdown(f"<div class='legs'>{sel.base}/{sel.quote} — {legs_label(sel)}</div>",
                    unsafe_allow_html=True)
        report = st.selectbox("Devise de reporting du P&L", CURRENCIES, index=0)

        p0, p1 = dict(P), dict(P)
        for ccy in {sel.base, sel.quote} - {"USD"}:
            c = CONTRACTS[ccy]
            fmt = "%.7f" if ccy == "JPY" else "%.5f"
            a, b = st.columns(2)
            p0[ccy] = a.number_input(f"{c.code} entrée", value=float(P[ccy]),
                                     step=c.tick, format=fmt, key=f"e_{ccy}")
            p1[ccy] = b.number_input(f"{c.code} sortie", value=float(P[ccy]),
                                     step=c.tick, format=fmt, key=f"s_{ccy}")

        r = pnl(sel, p0, p1, report)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"P&L total ({report})", f"{r['total_report']:,.2f}")
        k2.metric("dont cross pur", f"{r['pure_report']:,.2f}")
        k3.metric("dont résiduel USD", f"{r['residual_report']:,.2f}")
        k4.metric(f"{sel.base}/{sel.quote}",
                  fmt_rate(r["x1"], sel.quote),
                  f"{(r['x1']/r['x0']-1)*100:+.3f} %")

        if r["legs"]:
            st.dataframe(pd.DataFrame(r["legs"]), hide_index=True, width="stretch",
                         column_config={"P&L USD": st.column_config.NumberColumn(format="%,.2f $"),
                                        "Ticks": st.column_config.NumberColumn(format="%.1f")})

        # Scénarios : variation de chaque devise contre USD
        st.markdown("#### Carte de scénarios")
        rng = st.slider("Amplitude (%)", 0.5, 5.0, 2.0, 0.5)
        moves = np.round(np.linspace(-rng, rng, 9), 2)
        z = []
        for mq in moves:
            row = []
            for mb in moves:
                ps = dict(p0)
                if sel.base != "USD":
                    ps[sel.base] = p0[sel.base] * (1 + mb / 100)
                if sel.quote != "USD":
                    ps[sel.quote] = p0[sel.quote] * (1 + mq / 100)
                row.append(pnl(sel, p0, ps, report)["total_report"])
            z.append(row)
        fig = go.Figure(go.Heatmap(
            z=z, x=[f"{m:+}%" for m in moves], y=[f"{m:+}%" for m in moves],
            colorscale="RdYlGn", zmid=0, texttemplate="%{z:,.0f}",
            hovertemplate=f"{sel.base} vs USD %{{x}}<br>{sel.quote} vs USD %{{y}}"
                          f"<br>P&L %{{z:,.0f}} {report}<extra></extra>"))
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title=f"{sel.base} vs USD", yaxis_title=f"{sel.quote} vs USD",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#E5E7EB")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# =================== VUE DEPUIS UNE DEVISE ===================
with tab_matrix:
    ref = st.selectbox("Devise de référence", CURRENCIES, index=1, key="ref")
    ml = st.slider("Lots max", 1, 200, 50, key="ml")
    rows = []
    for ccy in CURRENCIES:
        if ccy == ref:
            continue
        cmb = best_combo(build_combos(ref, ccy, P, ml, 1))
        rows.append({"Paire": f"{ref}/{ccy}",
                     "Cours": fmt_rate(cross(ref, ccy, P), ccy),
                     "Meilleure combinaison": legs_label(cmb),
                     "Erreur %": cmb.error_pct * 100,
                     "Résiduel USD": cmb.residual_usd})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config=DF_FMT)

    st.markdown("#### Matrice des cours croisés")
    mat = pd.DataFrame([[cross(b, q, P) for q in CURRENCIES] for b in CURRENCIES],
                       index=CURRENCIES, columns=CURRENCIES)
    st.dataframe(mat.style.format("{:.5f}"), width="stretch")

# =================== PRIX ===================
with tab_prices:
    if st.button("🔄 Rafraîchir les prix"):
        cached_prices.clear()
        live, src = cached_prices()
        if live:
            st.session_state.prices = live
        st.session_state.src = src
        st.session_state.ts = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    st.caption("Vous pouvez saisir vos propres prix (ceux de votre plateforme d'exécution).")
    dfp = pd.DataFrame([{"Devise": k, "Contrat": CONTRACTS[k].code,
                         "Prix (USD/unité)": v} for k, v in P.items()])
    edited = st.data_editor(dfp, hide_index=True, width="stretch",
                            disabled=["Devise", "Contrat"],
                            column_config={"Prix (USD/unité)":
                                           st.column_config.NumberColumn(format="%.7f")})
    if st.button("✅ Appliquer"):
        st.session_state.prices = dict(zip(edited["Devise"], edited["Prix (USD/unité)"]))
        st.session_state.src = "Saisie manuelle"
        st.rerun()

    st.markdown("#### Spécifications")
    st.dataframe(pd.DataFrame([{"Contrat": c.code, "Devise": c.ccy, "Taille": c.size,
                                "Tick": c.tick, "Valeur tick $": c.tick_value}
                               for c in CONTRACTS.values()]),
                 hide_index=True, width="stretch")
