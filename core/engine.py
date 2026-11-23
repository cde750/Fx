import math
from dataclasses import dataclass
from .contracts import CONTRACTS

def usd_per(ccy, prices):
    return 1.0 if ccy == "USD" else prices[ccy]

def cross(base, quote, prices):
    """Prix de 1 BASE exprimé en QUOTE."""
    return usd_per(base, prices) / usd_per(quote, prices)

def pip_size(quote):
    return 0.01 if quote == "JPY" else 0.0001

@dataclass
class Combo:
    base: str
    quote: str
    n_base: int            # lots signés sur le future de la devise de base
    n_quote: int           # lots signés sur le future de la devise de cotation
    base_notional: float   # en devise de base
    quote_notional: float  # en devise de cotation
    error_pct: float       # écart vs ratio théorique
    residual_usd: float    # exposition USD non couverte
    implied_rate: float

    @property
    def total_lots(self):
        return abs(self.n_base) + abs(self.n_quote)

def theoretical_ratio(base, quote, prices):
    """Nombre de lots QUOTE par lot BASE pour une neutralité USD."""
    cb, cq = CONTRACTS[base], CONTRACTS[quote]
    return (cb.size * prices[base]) / (cq.size * prices[quote])

def build_combos(base, quote, prices, max_lots=50, direction=1):
    """direction = +1 : achat BASE/QUOTE ; -1 : vente."""
    if base == quote:
        return []
    out = []

    # Paire contre USD : une seule jambe, pas d'erreur de ratio
    if "USD" in (base, quote):
        for n in range(1, max_lots + 1):
            if quote == "USD":                       # ex. EUR/USD -> 6E
                c = CONTRACTS[base]
                nb, nq = direction * n, 0
                bn = n * c.size
                qn = bn * prices[base]
            else:                                    # ex. USD/JPY -> short 6J
                c = CONTRACTS[quote]
                nb, nq = 0, -direction * n
                qn = n * c.size
                bn = qn * prices[quote]
            out.append(Combo(base, quote, nb, nq, bn, qn, 0.0, 0.0, qn / bn))
        return out

    # Vrai cross : deux jambes
    cb, cq = CONTRACTS[base], CONTRACTS[quote]
    r = theoretical_ratio(base, quote, prices)
    for n in range(1, max_lots + 1):
        m = round(r * n)
        if m < 1:
            continue
        bn, qn = n * cb.size, m * cq.size
        usd_long = bn * prices[base]
        usd_short = qn * prices[quote]
        err = (m - r * n) / (r * n)
        resid = -direction * (usd_long - usd_short)
        out.append(Combo(base, quote, direction * n, -direction * m,
                         bn, qn, err, resid, qn / bn))
    return out

def pareto(combos):
    """Combinaisons qui améliorent strictement l'erreur à mesure que la taille augmente."""
    best, res = math.inf, []
    for c in sorted(combos, key=lambda c: c.total_lots):
        if abs(c.error_pct) < best - 1e-12:
            res.append(c)
            best = abs(c.error_pct)
    return res

def best_combo(combos):
    return min(combos, key=lambda c: (abs(c.error_pct), c.total_lots)) if combos else None

def pnl(combo, p0, p1, report="USD"):
    """P&L détaillé par jambe, total, et décomposition cross / résiduel."""
    legs, total = [], 0.0
    for ccy, n in ((combo.base, combo.n_base), (combo.quote, combo.n_quote)):
        if ccy == "USD" or n == 0:
            continue
        c = CONTRACTS[ccy]
        d = p1[ccy] - p0[ccy]
        usd = n * c.size * d
        legs.append({"Contrat": c.code, "Lots": n, "Entrée": p0[ccy],
                     "Sortie": p1[ccy], "Ticks": d / c.tick, "P&L USD": usd})
        total += usd

    # P&L « pur cross » : nominal base × variation du cross, converti en USD
    sign = 1 if (combo.n_base > 0 or combo.n_quote < 0) else -1
    x0 = cross(combo.base, combo.quote, p0)
    x1 = cross(combo.base, combo.quote, p1)
    if combo.base == "USD":
        bn0 = combo.quote_notional / x0
    else:
        bn0 = combo.base_notional
    pure_usd = sign * bn0 * (x1 - x0) * usd_per(combo.quote, p1)

    fx = usd_per(report, p1)
    return {
        "legs": legs,
        "total_usd": total,
        "total_report": total / fx,
        "pure_report": pure_usd / fx,
        "residual_report": (total - pure_usd) / fx,
        "x0": x0, "x1": x1,
    }

def pip_value(combo, prices, report="USD"):
    """Valeur d'un pip du cross pour la position."""
    if combo.base == "USD":
        bn = combo.quote_notional / cross(combo.base, combo.quote, prices)
    else:
        bn = combo.base_notional
    v_quote = bn * pip_size(combo.quote)
    return v_quote * usd_per(combo.quote, prices) / usd_per(report, prices)
