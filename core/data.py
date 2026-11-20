from .contracts import CONTRACTS

# Valeurs de secours (USD par unité de devise), à éditer dans l'app
DEFAULT_PRICES = {
    "EUR": 1.1600, "GBP": 1.3100, "JPY": 0.0065000, "CHF": 1.2500,
    "AUD": 0.6500, "NZD": 0.5700, "CAD": 0.7150,
}

def fetch_prices():
    """Derniers prix des futures via Yahoo (données différées)."""
    try:
        import yfinance as yf
        out = {}
        for ccy, c in CONTRACTS.items():
            h = yf.Ticker(c.yf).history(period="5d", interval="1d")
            if h.empty:
                raise ValueError(c.yf)
            out[ccy] = float(h["Close"].iloc[-1])
        return out, "Yahoo Finance (différé)"
    except Exception:
        return None, "Valeurs par défaut"
