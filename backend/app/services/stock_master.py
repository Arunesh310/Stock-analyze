"""Stock master database — the single source of truth for tradable symbols.

This module replaces the small `universe.py` hard-coded map with a richer,
curated catalogue of Indian listed companies (NSE primary, BSE as an alias).

Each entry carries:

- ``symbol`` (yfinance-formatted, e.g. ``RELIANCE.NS``)
- ``nse``    — bare NSE ticker (e.g. ``RELIANCE``)
- ``bse``    — BSE ticker / scrip code if known
- ``name``   — display name
- ``sector`` / ``industry``
- ``market_cap`` bucket (large / mid / small)
- ``aliases`` — list of strings used for search / typo-tolerant lookup

The module exposes high-level helpers used by:

- the symbol *normalizer* (``RELIANCE`` -> ``RELIANCE.NS``, ``reliance`` -> …)
- the search/autocomplete router
- the AI engine's sector-aware logic

``universe.py`` continues to work — it now wraps `stock_master` for
backwards compatibility — so nothing existing breaks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class StockMeta:
    symbol: str          # yfinance: TICKER.NS / TICKER.BO
    nse: Optional[str]   # bare NSE ticker (no suffix)
    bse: Optional[str]   # BSE 6-digit scrip code as string
    name: str
    sector: str
    industry: str
    market_cap: str      # "large" | "mid" | "small" | "index" | "fx" | "commodity"
    exchange: str        # "NSE" | "BSE" | "INDEX" | "FX" | "COMM"
    aliases: tuple = field(default_factory=tuple)

    def matches(self, q: str) -> bool:
        ql = q.lower()
        haystacks = [
            self.symbol.lower(),
            (self.nse or "").lower(),
            (self.bse or "").lower(),
            self.name.lower(),
            self.sector.lower(),
            self.industry.lower(),
        ] + [a.lower() for a in self.aliases]
        return any(ql in h for h in haystacks if h)


# ---------------------------------------------------------------------------
# Master list. Curated to balance coverage vs maintainability.
# The shape (sector, industry, cap) is set conservatively; aliases lean on
# the common short names that retail users actually type.
# ---------------------------------------------------------------------------


def _e(
    sym: str,
    name: str,
    sector: str,
    industry: str,
    *,
    bse: Optional[str] = None,
    cap: str = "large",
    aliases: Iterable[str] = (),
    exchange: str = "NSE",
) -> StockMeta:
    nse = sym.split(".")[0] if sym.endswith(".NS") else None
    return StockMeta(
        symbol=sym,
        nse=nse,
        bse=bse,
        name=name,
        sector=sector,
        industry=industry,
        market_cap=cap,
        exchange=exchange,
        aliases=tuple(aliases),
    )


_STOCKS: List[StockMeta] = [
    # =================== Banks ===================
    _e("HDFCBANK.NS", "HDFC Bank", "Banking", "Private Bank", bse="500180",
       aliases=["hdfc bank", "hdfcb"]),
    _e("ICICIBANK.NS", "ICICI Bank", "Banking", "Private Bank", bse="532174",
       aliases=["icici", "icici bank"]),
    _e("SBIN.NS", "State Bank of India", "Banking", "PSU Bank", bse="500112",
       aliases=["sbi", "state bank"]),
    _e("AXISBANK.NS", "Axis Bank", "Banking", "Private Bank", bse="532215",
       aliases=["axis", "axisb"]),
    _e("KOTAKBANK.NS", "Kotak Mahindra Bank", "Banking", "Private Bank", bse="500247",
       aliases=["kotak", "kmb"]),
    _e("INDUSINDBK.NS", "IndusInd Bank", "Banking", "Private Bank", bse="532187",
       aliases=["indusind"]),
    _e("BANKBARODA.NS", "Bank of Baroda", "Banking", "PSU Bank", bse="532134",
       aliases=["bob", "barodabank"]),
    _e("PNB.NS", "Punjab National Bank", "Banking", "PSU Bank", bse="532461",
       aliases=["punjab national"]),
    _e("CANBK.NS", "Canara Bank", "Banking", "PSU Bank", bse="532483", cap="mid",
       aliases=["canara"]),
    _e("UNIONBANK.NS", "Union Bank of India", "Banking", "PSU Bank", bse="532477", cap="mid"),
    _e("FEDERALBNK.NS", "Federal Bank", "Banking", "Private Bank", bse="500469", cap="mid",
       aliases=["federal"]),
    _e("IDFCFIRSTB.NS", "IDFC First Bank", "Banking", "Private Bank", bse="539437", cap="mid",
       aliases=["idfc first", "idfc"]),
    _e("YESBANK.NS", "Yes Bank", "Banking", "Private Bank", bse="532648", cap="mid",
       aliases=["yes"]),
    _e("AUBANK.NS", "AU Small Finance Bank", "Banking", "Small Finance Bank",
       bse="540611", cap="mid", aliases=["au sfb", "au bank"]),
    _e("BANDHANBNK.NS", "Bandhan Bank", "Banking", "Private Bank", bse="541153", cap="mid",
       aliases=["bandhan"]),
    _e("RBLBANK.NS", "RBL Bank", "Banking", "Private Bank", bse="540065", cap="mid",
       aliases=["rbl"]),

    # =================== NBFCs / Finance ===================
    _e("BAJFINANCE.NS", "Bajaj Finance", "NBFC", "Consumer Finance", bse="500034",
       aliases=["bajaj fin", "bajfin"]),
    _e("BAJAJFINSV.NS", "Bajaj Finserv", "NBFC", "Diversified Financials", bse="532978",
       aliases=["bajaj finserv"]),
    _e("CHOLAFIN.NS", "Cholamandalam Investment & Finance", "NBFC",
       "Vehicle Finance", bse="511243", cap="mid", aliases=["chola", "cholaman"]),
    _e("SHRIRAMFIN.NS", "Shriram Finance", "NBFC", "Vehicle Finance", bse="511218",
       cap="large", aliases=["shriram", "stfc"]),
    _e("MUTHOOTFIN.NS", "Muthoot Finance", "NBFC", "Gold Finance", bse="533398", cap="mid",
       aliases=["muthoot"]),
    _e("LICHSGFIN.NS", "LIC Housing Finance", "NBFC", "Housing Finance", bse="500253",
       cap="mid", aliases=["lic housing"]),
    _e("PFC.NS", "Power Finance Corp", "NBFC", "Infra Finance", bse="532810", cap="mid",
       aliases=["pfc india"]),
    _e("RECLTD.NS", "REC Ltd", "NBFC", "Infra Finance", bse="532955", cap="mid",
       aliases=["rec", "rural electrification"]),
    _e("SBICARD.NS", "SBI Cards & Payment", "NBFC", "Credit Cards", bse="543066",
       cap="mid", aliases=["sbi cards"]),
    _e("HDFCLIFE.NS", "HDFC Life Insurance", "Insurance", "Life Insurance",
       bse="540777", cap="large", aliases=["hdfc life"]),
    _e("SBILIFE.NS", "SBI Life Insurance", "Insurance", "Life Insurance",
       bse="540719", cap="large", aliases=["sbi life"]),
    _e("ICICIPRULI.NS", "ICICI Prudential Life", "Insurance", "Life Insurance",
       bse="540133", cap="mid", aliases=["icici pru"]),
    _e("ICICIGI.NS", "ICICI Lombard General Ins", "Insurance",
       "General Insurance", bse="540716", cap="mid", aliases=["icici lombard"]),
    _e("LICI.NS", "Life Insurance Corp", "Insurance", "Life Insurance",
       bse="543526", cap="large", aliases=["lic"]),

    # =================== IT ===================
    _e("TCS.NS", "Tata Consultancy Services", "IT", "IT Services", bse="532540",
       aliases=["tcs", "tata cs"]),
    _e("INFY.NS", "Infosys", "IT", "IT Services", bse="500209",
       aliases=["infy", "infosys ltd"]),
    _e("WIPRO.NS", "Wipro", "IT", "IT Services", bse="507685"),
    _e("HCLTECH.NS", "HCL Technologies", "IT", "IT Services", bse="532281",
       aliases=["hcl"]),
    _e("TECHM.NS", "Tech Mahindra", "IT", "IT Services", bse="532755",
       aliases=["techm", "tech m"]),
    _e("LTIM.NS", "LTIMindtree", "IT", "IT Services", bse="540005", cap="mid",
       aliases=["lti", "mindtree"]),
    _e("PERSISTENT.NS", "Persistent Systems", "IT", "IT Services", bse="533179",
       cap="mid", aliases=["persistent"]),
    _e("COFORGE.NS", "Coforge", "IT", "IT Services", bse="532541", cap="mid",
       aliases=["coforge", "niit tech"]),
    _e("MPHASIS.NS", "Mphasis", "IT", "IT Services", bse="526299", cap="mid"),
    _e("LTTS.NS", "L&T Technology Services", "IT", "Engineering R&D",
       bse="540115", cap="mid", aliases=["ltts"]),
    _e("OFSS.NS", "Oracle Financial Services", "IT", "Financial Software",
       bse="532466", cap="mid", aliases=["ofss", "oracle india"]),
    _e("CYIENT.NS", "Cyient", "IT", "Engineering R&D", bse="532175", cap="small"),
    _e("KPITTECH.NS", "KPIT Technologies", "IT", "Auto Software", bse="542651",
       cap="mid", aliases=["kpit"]),

    # =================== Energy / Oil & Gas ===================
    _e("RELIANCE.NS", "Reliance Industries", "Energy", "Diversified", bse="500325",
       aliases=["ril", "reliance", "reliance ind"]),
    _e("ONGC.NS", "Oil & Natural Gas Corp", "Oil & Gas", "Upstream", bse="500312",
       aliases=["ongc"]),
    _e("IOC.NS", "Indian Oil Corp", "Oil & Gas", "Refining/Mktg", bse="530965",
       aliases=["indian oil", "iocl"]),
    _e("BPCL.NS", "Bharat Petroleum Corp", "Oil & Gas", "Refining/Mktg",
       bse="500547"),
    _e("HINDPETRO.NS", "Hindustan Petroleum Corp", "Oil & Gas", "Refining/Mktg",
       bse="500104", cap="mid", aliases=["hpcl"]),
    _e("GAIL.NS", "GAIL India", "Oil & Gas", "Gas Distribution", bse="532155"),
    _e("OIL.NS", "Oil India", "Oil & Gas", "Upstream", bse="533106", cap="mid",
       aliases=["oil india"]),
    _e("PETRONET.NS", "Petronet LNG", "Oil & Gas", "LNG", bse="532522", cap="mid",
       aliases=["petronet"]),
    _e("IGL.NS", "Indraprastha Gas", "Oil & Gas", "City Gas", bse="532514", cap="mid",
       aliases=["igl", "indraprastha"]),
    _e("MGL.NS", "Mahanagar Gas", "Oil & Gas", "City Gas", bse="539957", cap="small",
       aliases=["mgl", "mahanagar"]),

    # =================== Power / Utilities / Renewables ===================
    _e("NTPC.NS", "NTPC", "Power", "PSU Power Generation", bse="532555",
       aliases=["national thermal"]),
    _e("POWERGRID.NS", "Power Grid Corp", "Power", "Transmission", bse="532898",
       aliases=["pgcil", "powergrid"]),
    _e("TATAPOWER.NS", "Tata Power", "Power", "IPP", bse="500400",
       aliases=["tata pwr"]),
    _e("ADANIPOWER.NS", "Adani Power", "Power", "IPP", bse="533096", cap="mid"),
    _e("ADANIGREEN.NS", "Adani Green Energy", "Renewable", "Solar/Wind", bse="541450",
       aliases=["adani green"]),
    _e("ADANIENSOL.NS", "Adani Energy Solutions", "Power", "Transmission",
       bse="539254", cap="mid", aliases=["adani transmission"]),
    _e("JSWENERGY.NS", "JSW Energy", "Power", "IPP", bse="533148", cap="mid"),
    _e("SUZLON.NS", "Suzlon Energy", "Renewable", "Wind", bse="532667", cap="mid",
       aliases=["suzlon"]),
    _e("INOXWIND.NS", "Inox Wind", "Renewable", "Wind", bse="539083", cap="small",
       aliases=["inox wind"]),
    _e("NHPC.NS", "NHPC", "Power", "Hydro PSU", bse="533098", cap="mid"),
    _e("SJVN.NS", "SJVN", "Power", "Hydro PSU", bse="533206", cap="small"),

    # =================== Metals / Mining ===================
    _e("TATASTEEL.NS", "Tata Steel", "Metals", "Steel", bse="500470",
       aliases=["tatasteel"]),
    _e("JSWSTEEL.NS", "JSW Steel", "Metals", "Steel", bse="500228",
       aliases=["jsw"]),
    _e("HINDALCO.NS", "Hindalco Industries", "Metals", "Aluminium", bse="500440",
       aliases=["hindalco"]),
    _e("VEDL.NS", "Vedanta", "Metals", "Diversified Metals", bse="500295",
       aliases=["vedanta"]),
    _e("COALINDIA.NS", "Coal India", "Metals", "Coal", bse="533278",
       aliases=["coal india"]),
    _e("NMDC.NS", "NMDC", "Metals", "Iron Ore", bse="526371", cap="mid"),
    _e("SAIL.NS", "Steel Authority of India", "Metals", "Steel", bse="500113",
       cap="mid", aliases=["sail"]),
    _e("JINDALSTEL.NS", "Jindal Steel & Power", "Metals", "Steel", bse="532286",
       cap="mid", aliases=["jindal", "jspl"]),
    _e("HINDZINC.NS", "Hindustan Zinc", "Metals", "Zinc", bse="500188",
       aliases=["hzl", "hindustan zinc"]),
    _e("NATIONALUM.NS", "National Aluminium", "Metals", "Aluminium PSU",
       bse="532234", cap="mid", aliases=["nalco"]),

    # =================== Auto ===================
    _e("TATAMOTORS.NS", "Tata Motors", "Auto", "OEM", bse="500570",
       aliases=["tata motors"]),
    _e("M&M.NS", "Mahindra & Mahindra", "Auto", "OEM",
       bse="500520", aliases=["mahindra", "m&m"]),
    _e("MARUTI.NS", "Maruti Suzuki India", "Auto", "OEM", bse="532500",
       aliases=["maruti"]),
    _e("BAJAJ-AUTO.NS", "Bajaj Auto", "Auto", "2W/3W", bse="532977",
       aliases=["bajaj auto"]),
    _e("EICHERMOT.NS", "Eicher Motors", "Auto", "2W/CV", bse="505200",
       aliases=["eicher", "royal enfield"]),
    _e("HEROMOTOCO.NS", "Hero MotoCorp", "Auto", "2W", bse="500182",
       aliases=["hero"]),
    _e("TVSMOTOR.NS", "TVS Motor", "Auto", "2W", bse="532343",
       aliases=["tvs"]),
    _e("ASHOKLEY.NS", "Ashok Leyland", "Auto", "CV", bse="500477", cap="mid",
       aliases=["ashok leyland"]),
    _e("MOTHERSON.NS", "Samvardhana Motherson", "Auto", "Components",
       bse="517334", cap="mid", aliases=["motherson"]),
    _e("BOSCHLTD.NS", "Bosch", "Auto", "Components", bse="500530", cap="mid"),
    _e("BALKRISIND.NS", "Balkrishna Industries", "Auto", "Tyres",
       bse="502355", cap="mid", aliases=["balkrishna"]),
    _e("MRF.NS", "MRF", "Auto", "Tyres", bse="500290", cap="mid"),
    _e("APOLLOTYRE.NS", "Apollo Tyres", "Auto", "Tyres", bse="500877", cap="mid"),
    _e("EXIDEIND.NS", "Exide Industries", "Auto", "Batteries", bse="500086", cap="mid",
       aliases=["exide"]),

    # =================== FMCG ===================
    _e("HINDUNILVR.NS", "Hindustan Unilever", "FMCG", "Personal Care",
       bse="500696", aliases=["hul", "unilever"]),
    _e("ITC.NS", "ITC", "FMCG", "Diversified", bse="500875"),
    _e("NESTLEIND.NS", "Nestle India", "FMCG", "Food", bse="500790",
       aliases=["nestle"]),
    _e("BRITANNIA.NS", "Britannia Industries", "FMCG", "Food", bse="500825"),
    _e("DABUR.NS", "Dabur India", "FMCG", "Personal Care", bse="500096"),
    _e("MARICO.NS", "Marico", "FMCG", "Personal Care", bse="531642", cap="mid"),
    _e("GODREJCP.NS", "Godrej Consumer Products", "FMCG", "Personal Care",
       bse="532424", cap="mid", aliases=["godrej cp", "gcpl"]),
    _e("COLPAL.NS", "Colgate-Palmolive India", "FMCG", "Oral Care",
       bse="500830", cap="mid", aliases=["colgate"]),
    _e("TATACONSUM.NS", "Tata Consumer Products", "FMCG", "Food/Beverage",
       bse="500800", aliases=["tata consumer", "tata tea"]),
    _e("UBL.NS", "United Breweries", "FMCG", "Beverages", bse="532478",
       cap="mid", aliases=["united breweries", "kingfisher"]),
    _e("VBL.NS", "Varun Beverages", "FMCG", "Beverages", bse="540180",
       aliases=["varun bev"]),

    # =================== Pharma / Healthcare ===================
    _e("SUNPHARMA.NS", "Sun Pharmaceutical", "Pharma", "Generics", bse="524715",
       aliases=["sun pharma"]),
    _e("DRREDDY.NS", "Dr Reddy's Laboratories", "Pharma", "Generics",
       bse="500124", aliases=["dr reddy", "drl"]),
    _e("CIPLA.NS", "Cipla", "Pharma", "Generics", bse="500087"),
    _e("DIVISLAB.NS", "Divi's Laboratories", "Pharma", "API", bse="532488",
       aliases=["divis"]),
    _e("LUPIN.NS", "Lupin", "Pharma", "Generics", bse="500257", cap="mid"),
    _e("TORNTPHARM.NS", "Torrent Pharmaceuticals", "Pharma", "Generics",
       bse="500420", cap="mid", aliases=["torrent pharma"]),
    _e("AUROPHARMA.NS", "Aurobindo Pharma", "Pharma", "Generics", bse="524804",
       cap="mid", aliases=["aurobindo"]),
    _e("ZYDUSLIFE.NS", "Zydus Lifesciences", "Pharma", "Generics", bse="532321",
       cap="mid", aliases=["zydus", "cadila"]),
    _e("BIOCON.NS", "Biocon", "Pharma", "Biologics", bse="532523", cap="mid"),
    _e("APOLLOHOSP.NS", "Apollo Hospitals", "Healthcare", "Hospitals",
       bse="508869", aliases=["apollo hosp"]),
    _e("MAXHEALTH.NS", "Max Healthcare", "Healthcare", "Hospitals",
       bse="543220", cap="mid", aliases=["max health"]),
    _e("FORTIS.NS", "Fortis Healthcare", "Healthcare", "Hospitals",
       bse="532843", cap="mid"),
    _e("LAURUSLABS.NS", "Laurus Labs", "Pharma", "API", bse="540222", cap="mid",
       aliases=["laurus"]),

    # =================== Defence / PSU / Capital Goods ===================
    _e("HAL.NS", "Hindustan Aeronautics", "Defence", "Aerospace", bse="541154",
       aliases=["hal", "hal india"]),
    _e("BEL.NS", "Bharat Electronics", "Defence", "Electronics", bse="500049",
       aliases=["bel"]),
    _e("BDL.NS", "Bharat Dynamics", "Defence", "Missiles", bse="541143", cap="mid",
       aliases=["bdl"]),
    _e("MAZDOCK.NS", "Mazagon Dock Shipbuilders", "Defence", "Shipbuilding",
       bse="543237", cap="mid", aliases=["mazagon", "mdl"]),
    _e("COCHINSHIP.NS", "Cochin Shipyard", "Defence", "Shipbuilding",
       bse="540678", cap="mid", aliases=["cochin"]),
    _e("PARAS.NS", "Paras Defence & Space", "Defence", "Defence Electronics",
       bse="543322", cap="small", aliases=["paras"]),
    _e("ZENTEC.NS", "Zen Technologies", "Defence", "Simulators", bse="533339",
       cap="small", aliases=["zen tech"]),
    _e("DATAPATTNS.NS", "Data Patterns India", "Defence", "Defence Electronics",
       bse="543428", cap="small", aliases=["data patterns"]),
    _e("L&TFH.NS", "L&T Finance Holdings", "NBFC", "Diversified Finance",
       bse="533519", cap="mid", aliases=["l&t finance", "ltfh"]),
    _e("LT.NS", "Larsen & Toubro", "Capital Goods", "Engineering & Construction",
       bse="500510", aliases=["l&t", "lt"]),
    _e("SIEMENS.NS", "Siemens India", "Capital Goods", "Electrical Equipment",
       bse="500550", aliases=["siemens"]),
    _e("ABB.NS", "ABB India", "Capital Goods", "Electrical Equipment",
       bse="500002", cap="mid"),
    _e("CUMMINSIND.NS", "Cummins India", "Capital Goods", "Engines",
       bse="500480", cap="mid", aliases=["cummins"]),
    _e("BHEL.NS", "Bharat Heavy Electricals", "Capital Goods", "Power Equipment",
       bse="500103", cap="mid", aliases=["bhel"]),
    _e("HONAUT.NS", "Honeywell Automation", "Capital Goods", "Automation",
       bse="517174", cap="small", aliases=["honeywell"]),

    # =================== Railways / Infra ===================
    _e("IRFC.NS", "Indian Railway Finance Corp", "Railways", "Rail Finance",
       bse="543257", cap="mid", aliases=["irfc"]),
    _e("RVNL.NS", "Rail Vikas Nigam", "Railways", "Rail EPC", bse="542649",
       cap="mid", aliases=["rvnl"]),
    _e("IRCTC.NS", "Indian Railway Catering", "Railways", "Rail Services",
       bse="542830", cap="mid", aliases=["irctc"]),
    _e("RAILTEL.NS", "RailTel Corp", "Railways", "Rail Telecom",
       bse="543265", cap="small", aliases=["railtel"]),
    _e("TITAGARH.NS", "Titagarh Rail Systems", "Railways", "Rolling Stock",
       bse="532966", cap="mid", aliases=["titagarh"]),
    _e("IRCON.NS", "IRCON International", "Railways", "Rail EPC",
       bse="541956", cap="small", aliases=["ircon"]),
    _e("CONCOR.NS", "Container Corp of India", "Logistics", "Rail Logistics",
       bse="531344", cap="mid", aliases=["concor"]),
    _e("ADANIPORTS.NS", "Adani Ports & SEZ", "Logistics", "Ports",
       bse="532921", aliases=["adani ports"]),
    _e("GMRINFRA.NS", "GMR Airports Infra", "Infrastructure", "Airports",
       bse="532754", cap="mid", aliases=["gmr"]),

    # =================== Adani Group ===================
    _e("ADANIENT.NS", "Adani Enterprises", "Conglomerate", "Diversified",
       bse="512599", aliases=["adani"]),
    _e("ATGL.NS", "Adani Total Gas", "Oil & Gas", "City Gas",
       bse="542066", cap="mid", aliases=["adani gas"]),
    _e("ACC.NS", "ACC", "Cement", "Cement", bse="500410", cap="mid"),
    _e("AMBUJACEM.NS", "Ambuja Cements", "Cement", "Cement", bse="500425",
       cap="mid", aliases=["ambuja"]),

    # =================== Telecom ===================
    _e("BHARTIARTL.NS", "Bharti Airtel", "Telecom", "Telecom Services",
       bse="532454", aliases=["airtel", "bharti"]),
    _e("IDEA.NS", "Vodafone Idea", "Telecom", "Telecom Services", bse="532822",
       cap="mid", aliases=["vi", "vodafone idea"]),
    _e("INDUSTOWER.NS", "Indus Towers", "Telecom", "Telecom Infra", bse="534816",
       cap="mid"),
    _e("TATACOMM.NS", "Tata Communications", "Telecom", "Data Services",
       bse="500483", cap="mid"),

    # =================== Cement / Building Materials ===================
    _e("ULTRACEMCO.NS", "UltraTech Cement", "Cement", "Cement", bse="532538",
       aliases=["ultratech"]),
    _e("GRASIM.NS", "Grasim Industries", "Cement", "Diversified", bse="500300",
       aliases=["grasim"]),
    _e("SHREECEM.NS", "Shree Cement", "Cement", "Cement", bse="500387"),
    _e("DALBHARAT.NS", "Dalmia Bharat", "Cement", "Cement", bse="542216", cap="mid",
       aliases=["dalmia"]),
    _e("RAMCOCEM.NS", "Ramco Cements", "Cement", "Cement", bse="500260",
       cap="mid", aliases=["ramco"]),

    # =================== Paints / Chemicals ===================
    _e("ASIANPAINT.NS", "Asian Paints", "Paints", "Paints", bse="500820"),
    _e("BERGEPAINT.NS", "Berger Paints", "Paints", "Paints", bse="509480", cap="mid",
       aliases=["berger"]),
    _e("KANSAINER.NS", "Kansai Nerolac Paints", "Paints", "Paints",
       bse="500165", cap="small", aliases=["nerolac"]),
    _e("PIDILITIND.NS", "Pidilite Industries", "Chemicals", "Adhesives",
       bse="500331", aliases=["pidilite", "fevicol"]),
    _e("SRF.NS", "SRF Ltd", "Chemicals", "Specialty Chemicals", bse="503806",
       cap="mid"),
    _e("UPL.NS", "UPL Ltd", "Chemicals", "Agrochemicals", bse="512070",
       cap="mid"),
    _e("DEEPAKNTR.NS", "Deepak Nitrite", "Chemicals", "Specialty Chemicals",
       bse="506401", cap="mid", aliases=["deepak"]),
    _e("AARTIIND.NS", "Aarti Industries", "Chemicals", "Specialty Chemicals",
       bse="524208", cap="mid", aliases=["aarti"]),
    _e("PIIND.NS", "PI Industries", "Chemicals", "Agrochemicals",
       bse="523642", cap="mid", aliases=["pi ind"]),

    # =================== Realty ===================
    _e("DLF.NS", "DLF", "Realty", "Residential/Commercial", bse="532868"),
    _e("GODREJPROP.NS", "Godrej Properties", "Realty", "Residential",
       bse="533150", cap="mid", aliases=["godrej prop"]),
    _e("OBEROIRLTY.NS", "Oberoi Realty", "Realty", "Residential",
       bse="533273", cap="mid", aliases=["oberoi"]),
    _e("PRESTIGE.NS", "Prestige Estates", "Realty", "Residential",
       bse="533274", cap="mid", aliases=["prestige"]),
    _e("BRIGADE.NS", "Brigade Enterprises", "Realty", "Residential",
       bse="532929", cap="small", aliases=["brigade"]),
    _e("PHOENIXLTD.NS", "Phoenix Mills", "Realty", "Mall Operator",
       bse="503100", cap="mid", aliases=["phoenix"]),

    # =================== Aviation / Hospitality ===================
    _e("INDIGO.NS", "InterGlobe Aviation", "Aviation", "Airlines", bse="539448",
       aliases=["indigo", "interglobe"]),
    _e("SPICEJET.NS", "SpiceJet", "Aviation", "Airlines", bse="500285",
       cap="small", aliases=["spicejet"]),
    _e("INDHOTEL.NS", "Indian Hotels (Taj)", "Hospitality", "Hotels",
       bse="500850", cap="mid", aliases=["taj", "indian hotels"]),
    _e("LEMONTREE.NS", "Lemon Tree Hotels", "Hospitality", "Hotels",
       bse="541233", cap="small", aliases=["lemon tree"]),

    # =================== Consumer / Retail / Lifestyle ===================
    _e("TITAN.NS", "Titan Company", "Consumer", "Watches/Jewellery", bse="500114",
       aliases=["titan"]),
    _e("DMART.NS", "Avenue Supermarts", "Retail", "Grocery Retail",
       bse="540376", aliases=["dmart", "avenue supermarts"]),
    _e("TRENT.NS", "Trent", "Retail", "Apparel Retail", bse="500251"),
    _e("PAGEIND.NS", "Page Industries", "Consumer", "Apparel", bse="532827", cap="mid",
       aliases=["jockey", "page"]),
    _e("ZOMATO.NS", "Eternal (Zomato)", "Internet", "Food Delivery", bse="543320",
       aliases=["zomato", "eternal"]),
    _e("NYKAA.NS", "FSN E-Commerce Ventures (Nykaa)", "Internet", "E-commerce",
       bse="543384", cap="mid", aliases=["nykaa", "fsn"]),
    _e("PAYTM.NS", "One97 Communications (Paytm)", "Internet", "Fintech",
       bse="543396", cap="mid", aliases=["paytm", "one97"]),
    _e("POLICYBZR.NS", "PB Fintech (PolicyBazaar)", "Internet", "Fintech",
       bse="543390", cap="mid", aliases=["policybazaar", "pb fintech"]),
    _e("IRCTC.BO", "IRCTC (BSE)", "Railways", "Rail Services", bse="542830",
       cap="mid", exchange="BSE", aliases=["irctc bse"]),

    # =================== Misc industrials ===================
    _e("HAVELLS.NS", "Havells India", "Consumer Durables", "Electricals",
       bse="517354", aliases=["havells"]),
    _e("VOLTAS.NS", "Voltas", "Consumer Durables", "ACs", bse="500575",
       cap="mid", aliases=["voltas"]),
    _e("BLUESTARCO.NS", "Blue Star", "Consumer Durables", "ACs",
       bse="500067", cap="mid", aliases=["blue star"]),
    _e("WHIRLPOOL.NS", "Whirlpool India", "Consumer Durables", "Appliances",
       bse="500238", cap="mid", aliases=["whirlpool"]),
    _e("CROMPTON.NS", "Crompton Greaves Consumer", "Consumer Durables",
       "Appliances", bse="539876", cap="mid", aliases=["crompton"]),
    _e("DIXON.NS", "Dixon Technologies", "EMS", "Contract Manufacturing",
       bse="540699", cap="mid", aliases=["dixon"]),

    # =================== Indices / FX / Commodities ===================
    _e("^NSEI", "Nifty 50", "Index", "Benchmark", cap="index", exchange="INDEX",
       aliases=["nifty", "nifty50"]),
    _e("^NSEBANK", "Nifty Bank", "Index", "Banking", cap="index", exchange="INDEX",
       aliases=["bank nifty", "banknifty"]),
    _e("^CNXIT", "Nifty IT", "Index", "IT", cap="index", exchange="INDEX"),
    _e("^CNXAUTO", "Nifty Auto", "Index", "Auto", cap="index", exchange="INDEX"),
    _e("^CNXPHARMA", "Nifty Pharma", "Index", "Pharma", cap="index", exchange="INDEX"),
    _e("^CNXFMCG", "Nifty FMCG", "Index", "FMCG", cap="index", exchange="INDEX"),
    _e("^CNXENERGY", "Nifty Energy", "Index", "Energy", cap="index", exchange="INDEX"),
    _e("^CNXMETAL", "Nifty Metal", "Index", "Metals", cap="index", exchange="INDEX"),
    _e("^INDIAVIX", "India VIX", "Index", "Volatility", cap="index",
       exchange="INDEX", aliases=["vix", "india vix"]),
    _e("INR=X", "USD / INR", "FX", "Currency", cap="fx", exchange="FX",
       aliases=["usdinr", "rupee", "usd"]),
    _e("CL=F", "Crude Oil (WTI)", "Commodity", "Energy", cap="commodity",
       exchange="COMM", aliases=["crude", "oil"]),
    _e("GC=F", "Gold (COMEX)", "Commodity", "Precious Metals", cap="commodity",
       exchange="COMM", aliases=["gold"]),
    _e("SI=F", "Silver (COMEX)", "Commodity", "Precious Metals", cap="commodity",
       exchange="COMM", aliases=["silver"]),
]


# ---------------------------------------------------------------------------
# Extend coverage with bundled / fetched NSE list (additive — curated entries
# above with their aliases keep priority).
# ---------------------------------------------------------------------------


def _seen_symbols() -> set[str]:
    return {s.symbol.upper() for s in _STOCKS}


def _merge_from_extended() -> None:
    try:
        from ..data.nse_extended import EXTENDED_NSE  # noqa: WPS433
    except Exception:
        return
    have = _seen_symbols()
    for nse, name, sector, industry, cap in EXTENDED_NSE:
        sym = f"{nse}.NS"
        if sym.upper() in have:
            continue
        _STOCKS.append(_e(sym, name, sector, industry, cap=cap))
        have.add(sym.upper())


def _merge_from_nse_fetcher() -> None:
    """Pull NSE's full equity list at startup (best-effort, cached)."""
    try:
        from . import nse_master_fetcher  # noqa: WPS433
        rows = nse_master_fetcher.fetch_equity_rows()
    except Exception:
        rows = []
    if not rows:
        return
    have = _seen_symbols()
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        if not sym or sym in have:
            continue
        _STOCKS.append(
            StockMeta(
                symbol=sym,
                nse=r.get("nse"),
                bse=None,
                name=r.get("name") or sym,
                sector="Other",
                industry="",
                market_cap="",
                exchange="NSE",
                aliases=(),
            )
        )
        have.add(sym)


_merge_from_extended()
_merge_from_nse_fetcher()


# ---------------------------------------------------------------------------
# Indexes for fast lookup
# ---------------------------------------------------------------------------

_BY_SYMBOL: Dict[str, StockMeta] = {}
_BY_NSE: Dict[str, StockMeta] = {}
_BY_BSE: Dict[str, StockMeta] = {}
_BY_ALIAS: Dict[str, StockMeta] = {}

for _s in _STOCKS:
    _BY_SYMBOL[_s.symbol.upper()] = _s
    if _s.nse:
        _BY_NSE[_s.nse.upper()] = _s
    if _s.bse:
        _BY_BSE[_s.bse] = _s
    for a in _s.aliases:
        _BY_ALIAS[a.lower()] = _s
    _BY_ALIAS[_s.name.lower()] = _s


def all_stocks() -> List[StockMeta]:
    return list(_STOCKS)


_CURATED_CAP_WEIGHT = {"large": 0, "mid": 1, "small": 2, "": 3, None: 3}


def all_symbols() -> List[str]:
    return [s.symbol for s in _STOCKS if s.exchange == "NSE"]


def all_tradable_symbols() -> List[str]:
    return [s.symbol for s in _STOCKS if s.exchange in {"NSE", "BSE"}]


def liquid_symbols(limit: int = 80) -> List[str]:
    """A short, fast-loading subset for dashboards / WS ticks.

    Heuristic ordering: large > mid > small > unknown; preserves curated order
    so the most actively traded names are at the front of the list.
    """
    ordered = sorted(
        (s for s in _STOCKS if s.exchange == "NSE"),
        key=lambda s: _CURATED_CAP_WEIGHT.get(s.market_cap, 3),
    )
    return [s.symbol for s in ordered[:limit]]


def all_sectors() -> List[str]:
    return sorted({s.sector for s in _STOCKS if s.exchange == "NSE"})


def symbols_in_sector(sector: str) -> List[str]:
    return [
        s.symbol for s in _STOCKS
        if s.exchange == "NSE" and s.sector.lower() == sector.lower()
    ]


def find_by_symbol(symbol: str) -> Optional[StockMeta]:
    if not symbol:
        return None
    s = _BY_SYMBOL.get(symbol.upper())
    if s:
        return s
    nse = _BY_NSE.get(symbol.upper())
    if nse:
        return nse
    return _BY_BSE.get(symbol)


def find_by_alias(text: str) -> Optional[StockMeta]:
    if not text:
        return None
    return _BY_ALIAS.get(text.strip().lower())


def get_name(symbol: str) -> str:
    s = find_by_symbol(symbol)
    return s.name if s else symbol


def get_sector(symbol: str) -> str:
    s = find_by_symbol(symbol)
    return s.sector if s else "Other"


def search(query: str, limit: int = 25) -> List[Dict[str, str]]:
    """Substring search across symbol/name/sector/aliases (no fuzzy here;
    fuzzy is done in ``symbol_normalizer.search``)."""
    q = (query or "").strip()
    if not q:
        return [
            {
                "symbol": s.symbol,
                "name": s.name,
                "sector": s.sector,
                "industry": s.industry,
                "exchange": s.exchange,
                "market_cap": s.market_cap,
            }
            for s in _STOCKS[:limit]
            if s.exchange == "NSE"
        ]
    out: List[Dict[str, str]] = []
    for s in _STOCKS:
        if s.matches(q):
            out.append(
                {
                    "symbol": s.symbol,
                    "name": s.name,
                    "sector": s.sector,
                    "industry": s.industry,
                    "exchange": s.exchange,
                    "market_cap": s.market_cap,
                }
            )
            if len(out) >= limit:
                break
    return out


def get_metadata_dict(symbol: str) -> Dict[str, str]:
    s = find_by_symbol(symbol)
    if s is None:
        return {
            "symbol": symbol,
            "name": symbol,
            "sector": "Other",
            "industry": "",
            "exchange": "NSE" if symbol.endswith(".NS") else "OTHER",
            "market_cap": "",
        }
    return {
        "symbol": s.symbol,
        "name": s.name,
        "nse": s.nse or "",
        "bse": s.bse or "",
        "sector": s.sector,
        "industry": s.industry,
        "exchange": s.exchange,
        "market_cap": s.market_cap,
    }
