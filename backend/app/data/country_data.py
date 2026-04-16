"""Country-to-exchange mappings for filtering available stocks."""

COUNTRY_EXCHANGES: dict[str, list[str]] = {
    "US": ["NYSE", "NMS", "NASDAQ", "AMEX", "NYQ", "NAS", "NGM", "NCM", "PCX"],
    "IL": ["TLV", "TAE"],
    "GB": ["LSE", "LON"],
    "DE": ["FRA", "GER", "XETRA"],
    "FR": ["PAR", "EPA"],
    "JP": ["JPX", "TYO"],
    "CN": ["SHA", "SHE"],
    "HK": ["HKG"],
    "CA": ["TSX", "TOR"],
    "AU": ["ASX"],
}


def get_allowed_exchanges(country_code: str) -> list[str]:
    """Return list of allowed exchange codes for a country. Defaults to US exchanges."""
    return COUNTRY_EXCHANGES.get(country_code.upper(), COUNTRY_EXCHANGES["US"])
