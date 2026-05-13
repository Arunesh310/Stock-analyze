"""Seed ChromaDB with notable historical Indian-market events.

Run:
    python -m app.scripts.seed_memory
"""
from __future__ import annotations

from loguru import logger

from ..logger import setup_logging
from ..services.memory_engine import get_memory_store


EVENTS = [
    {
        "id": "covid_2020_crash",
        "text": (
            "March 2020 COVID-19 pandemic crash: Nifty 50 fell ~38% from the "
            "January high to the March low. Pharma, IT and FMCG outperformed "
            "during the recovery. Hotels, aviation, banks and PSU stocks "
            "underperformed initially. Government and RBI stimulus eventually "
            "drove a strong recovery into 2021."
        ),
        "meta": {"category": "crash", "year": 2020, "impact": "high"},
    },
    {
        "id": "demonetisation_2016",
        "text": (
            "November 2016 Demonetisation: Cash-intensive sectors (consumer "
            "durables, jewellery, real estate, two-wheelers) initially "
            "underperformed. Digital-payment, fintech and select banks (HDFC, "
            "Kotak) benefited as deposits flooded into the formal system."
        ),
        "meta": {"category": "policy", "year": 2016, "impact": "medium"},
    },
    {
        "id": "adani_hindenburg_2023",
        "text": (
            "January 2023 Hindenburg report on the Adani group: Adani group "
            "stocks crashed 30-70% in days, dragging Nifty short-term. Indian "
            "equity benchmarks recovered quickly as broader earnings remained "
            "healthy. Long-term Adani recovered partially after stake sales."
        ),
        "meta": {"category": "company-specific", "year": 2023, "impact": "high"},
    },
    {
        "id": "rbi_repo_hike_cycle_2022_23",
        "text": (
            "RBI hiked repo rate from 4.0% to 6.5% across 2022-23 to combat "
            "post-COVID inflation. NBFCs, housing finance and consumer-loan "
            "businesses faced margin compression. Banks generally benefited "
            "from higher NIMs initially."
        ),
        "meta": {"category": "rates", "year": 2023, "impact": "high"},
    },
    {
        "id": "election_rally_2014",
        "text": (
            "May 2014 election outcome: BJP-led majority government drove a "
            "strong pre-election capex/infra rally. Cement, capital goods, "
            "PSU banks led; defensives (FMCG/IT) underperformed."
        ),
        "meta": {"category": "elections", "year": 2014, "impact": "medium"},
    },
    {
        "id": "election_2024_volatility",
        "text": (
            "June 4, 2024 election results: BJP got fewer seats than expected. "
            "PSU, defence and railway stocks corrected sharply intraday "
            "before recovering as the NDA coalition stayed in power. Capex "
            "themes consolidated, then resumed their uptrend."
        ),
        "meta": {"category": "elections", "year": 2024, "impact": "high"},
    },
    {
        "id": "russia_ukraine_2022",
        "text": (
            "Russia–Ukraine war (Feb 2022 onwards): Crude oil spiked above "
            "$120 briefly. Indian oil marketing companies (BPCL, IOC, HPCL) "
            "underperformed due to capped retail prices. ONGC, Oil India, and "
            "fertilisers benefited. Defence capex theme strengthened."
        ),
        "meta": {"category": "geopolitics", "year": 2022, "impact": "high"},
    },
    {
        "id": "budget_2024_capex",
        "text": (
            "Union Budget 2024-25 emphasised infrastructure capex and rural "
            "spending. Roads, railways (RVNL, IRCON, IRFC), defence (HAL, BEL) "
            "rallied. Capital-gains-tax tweak caused short-term selling pressure."
        ),
        "meta": {"category": "budget", "year": 2024, "impact": "medium"},
    },
    {
        "id": "fed_pivot_2023",
        "text": (
            "US Fed dovish pivot (Dec 2023): Risk-on globally; Indian IT (TCS, "
            "Infosys) rallied on hopes of revived US tech spending; midcap and "
            "smallcap indices outperformed."
        ),
        "meta": {"category": "global", "year": 2023, "impact": "medium"},
    },
    {
        "id": "crude_spike_playbook",
        "text": (
            "Generic playbook for crude spikes: Bullish for upstream "
            "(ONGC, Oil India), bearish for paint companies (Asian Paints, "
            "Berger), aviation (IndiGo), tyres, and OMCs when retail prices "
            "are capped. Watch INR depreciation as a second-order effect."
        ),
        "meta": {"category": "playbook", "year": 0, "impact": "medium"},
    },
    {
        "id": "war_playbook",
        "text": (
            "Generic playbook for geopolitical conflict / war: Defence stocks "
            "(HAL, BEL, BDL, Mazagon Dock, Cochin Shipyard, Paras Defence), "
            "shipbuilders, gold benefit. Aviation, paints, importers and IT "
            "(if global recession risk rises) tend to underperform."
        ),
        "meta": {"category": "playbook", "year": 0, "impact": "high"},
    },
    {
        "id": "rate_cut_playbook",
        "text": (
            "Generic playbook for rate-cut cycle: Banks/NBFCs, real estate, "
            "auto (financing-driven), and capex-heavy sectors benefit. "
            "Defensives (FMCG/IT) typically underperform in early cuts."
        ),
        "meta": {"category": "playbook", "year": 0, "impact": "medium"},
    },
]


def main() -> None:
    setup_logging()
    store = get_memory_store()
    if not store.enabled:
        logger.error("ChromaDB not available — cannot seed memory.")
        return
    for ev in EVENTS:
        store.add(ev["id"], ev["text"], ev["meta"])
    logger.info(f"Seeded {len(EVENTS)} historical events. Total in store: {store.count()}")


if __name__ == "__main__":
    main()
