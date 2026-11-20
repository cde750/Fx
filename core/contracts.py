from dataclasses import dataclass. 

@dataclass(frozen=True)
class Contract:
    code: str
    ccy: str
    name: str
    size: float      # taille du contrat en devise
    tick: float      # pas de cotation (USD par unité)
    yf: str          # ticker Yahoo

    @property
    def tick_value(self) -> float:
        return self.size * self.tick

# ⚠️ Vérifiez les spécifications à jour sur cmegroup.com
CONTRACTS = {
    "EUR": Contract("6E", "EUR", "Euro",                125_000,    0.00005,   "6E=F"),
    "GBP": Contract("6B", "GBP", "Livre sterling",       62_500,    0.0001,    "6B=F"),
    "JPY": Contract("6J", "JPY", "Yen japonais",     12_500_000,    0.0000005, "6J=F"),
    "CHF": Contract("6S", "CHF", "Franc suisse",        125_000,    0.00005,   "6S=F"),
    "AUD": Contract("6A", "AUD", "Dollar australien",   100_000,    0.00005,   "6A=F"),
    "NZD": Contract("6N", "NZD", "Dollar néo-zélandais",100_000,    0.00005,   "6N=F"),
    "CAD": Contract("6C", "CAD", "Dollar canadien",     100_000,    0.00005,   "6C=F"),
}

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]
