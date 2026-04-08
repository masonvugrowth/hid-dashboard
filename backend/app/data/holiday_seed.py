"""
Static holiday seed data for 25 source markets.
Each entry maps to one row in holiday_calendars.
All holiday names in English for consistency.
"""

def _h(code, name, hname, htype, ms, ds, me, de, dur, long, prop, notes=""):
    return {
        "country_code": code,
        "country_name": name,
        "holiday_name": hname,
        "holiday_type": htype,
        "month_start": ms,
        "day_start": ds,
        "month_end": me,
        "day_end": de,
        "duration_days": dur,
        "is_long_holiday": long,
        "travel_propensity": prop,
        "notes": notes,
        "data_source": "static",
    }


HOLIDAY_SEED = [
    # ── Vietnam (VN) ─────────────────────────────────────────────────────
    _h("VN", "Vietnam", "Lunar New Year (Tet)", "cultural", 1, 20, 2, 5, 9, True, "HIGH",
       "Biggest domestic travel surge — 7–10 day Lunar New Year holiday"),
    _h("VN", "Vietnam", "Reunification & Labour Day", "national", 4, 28, 5, 3, 5, True, "HIGH",
       "Apr 30 + May 1 combined — 4–5 day holiday block, peak domestic travel"),
    _h("VN", "Vietnam", "National Day", "national", 9, 1, 9, 4, 4, True, "MEDIUM",
       "Sep 2 Independence Day — 4-day weekend"),

    # ── Taiwan (TW) ──────────────────────────────────────────────────────
    _h("TW", "Taiwan", "Lunar New Year", "cultural", 1, 20, 2, 5, 9, True, "HIGH",
       "9-day holiday — massive outbound travel"),
    _h("TW", "Taiwan", "Dragon Boat Festival", "cultural", 6, 8, 6, 12, 3, False, "MEDIUM",
       "3-day weekend — moderate travel"),
    _h("TW", "Taiwan", "National Day (Double Ten)", "national", 10, 8, 10, 12, 4, True, "MEDIUM",
       "4-day weekend including surrounding days"),
    _h("TW", "Taiwan", "Mid-Autumn Festival", "cultural", 9, 15, 9, 18, 3, False, "MEDIUM",
       "3-day weekend — family-oriented travel"),

    # ── Japan (JP) ───────────────────────────────────────────────────────
    _h("JP", "Japan", "Golden Week", "national", 4, 27, 5, 6, 10, True, "HIGH",
       "Cluster of national holidays — very high outbound volume"),
    _h("JP", "Japan", "Obon Festival", "cultural", 8, 10, 8, 20, 10, True, "HIGH",
       "7–10 day summer holiday — peak outbound season"),
    _h("JP", "Japan", "New Year", "cultural", 12, 28, 1, 5, 7, True, "MEDIUM",
       "Traditional New Year — domestic focus, some outbound"),
    _h("JP", "Japan", "Silver Week", "national", 9, 18, 9, 23, 5, True, "MEDIUM",
       "4–5 day holiday when Equinox falls right"),

    # ── South Korea (KR) ─────────────────────────────────────────────────
    _h("KR", "South Korea", "Lunar New Year (Seollal)", "cultural", 1, 25, 2, 2, 5, True, "HIGH",
       "5-day Lunar New Year — heavy outbound"),
    _h("KR", "South Korea", "Harvest Festival (Chuseok)", "cultural", 9, 14, 9, 20, 5, True, "HIGH",
       "Korean Thanksgiving — 5-day holiday block"),
    _h("KR", "South Korea", "Summer Vacation", "school_break", 7, 20, 8, 20, 30, True, "HIGH",
       "School summer break — family travel peak"),

    # ── China (CN) ───────────────────────────────────────────────────────
    _h("CN", "China", "Spring Festival (Chinese New Year)", "cultural", 1, 21, 2, 5, 7, True, "HIGH",
       "7-day Golden Week — largest migration on earth"),
    _h("CN", "China", "National Day Golden Week", "national", 10, 1, 10, 7, 7, True, "HIGH",
       "7-day national holiday — massive outbound tourism"),
    _h("CN", "China", "Labour Day Holiday", "national", 4, 29, 5, 3, 5, True, "MEDIUM",
       "5-day extended holiday — growing outbound trend"),

    # ── USA (US) ─────────────────────────────────────────────────────────
    _h("US", "USA", "Summer Break", "school_break", 6, 1, 8, 31, 90, True, "HIGH",
       "School summer break — peak family travel season"),
    _h("US", "USA", "Thanksgiving Weekend", "national", 11, 22, 11, 26, 4, True, "MEDIUM",
       "4-day weekend — domestic heavy, some international"),
    _h("US", "USA", "Christmas – New Year", "cultural", 12, 20, 1, 3, 14, True, "HIGH",
       "10+ day holiday window — strong long-haul travel"),

    # ── Australia (AU) ───────────────────────────────────────────────────
    _h("AU", "Australia", "Summer Holiday (Dec–Jan)", "school_break", 12, 15, 1, 31, 45, True, "HIGH",
       "Southern hemisphere summer — peak outbound"),
    _h("AU", "Australia", "Easter", "religious", 3, 28, 4, 3, 4, True, "HIGH",
       "4-day long weekend — strong outbound travel"),
    _h("AU", "Australia", "Winter School Break", "school_break", 7, 1, 7, 14, 14, True, "MEDIUM",
       "2-week mid-year break — Southeast Asia popular"),

    # ── Thailand (TH) ───────────────────────────────────────────────────
    _h("TH", "Thailand", "Songkran (Thai New Year)", "cultural", 4, 12, 4, 16, 5, True, "HIGH",
       "Thai New Year water festival — peak outbound travel"),
    _h("TH", "Thailand", "New Year Holiday", "national", 12, 29, 1, 3, 5, True, "HIGH",
       "5-day New Year block"),

    # ── Singapore (SG) ──────────────────────────────────────────────────
    _h("SG", "Singapore", "School Holiday (Mar)", "school_break", 3, 10, 3, 18, 9, True, "HIGH",
       "March school break — family travel week"),
    _h("SG", "Singapore", "School Holiday (Jun)", "school_break", 5, 26, 6, 24, 28, True, "HIGH",
       "4-week mid-year break — peak family outbound"),
    _h("SG", "Singapore", "School Holiday (Sep)", "school_break", 9, 1, 9, 8, 7, True, "HIGH",
       "1-week September break"),
    _h("SG", "Singapore", "School Holiday (Dec)", "school_break", 11, 18, 12, 31, 42, True, "HIGH",
       "Year-end school break — strong outbound"),

    # ── Malaysia (MY) ───────────────────────────────────────────────────
    _h("MY", "Malaysia", "End of Ramadan (Hari Raya)", "religious", 3, 28, 4, 5, 5, True, "HIGH",
       "End of Ramadan — floating, biggest outbound surge"),
    _h("MY", "Malaysia", "School Holiday (Mar)", "school_break", 3, 22, 3, 30, 9, True, "HIGH",
       "Mid-term school break"),
    _h("MY", "Malaysia", "School Holiday (Jun)", "school_break", 5, 25, 6, 9, 14, True, "HIGH",
       "2-week mid-year break"),
    _h("MY", "Malaysia", "School Holiday (Aug)", "school_break", 8, 17, 8, 25, 9, True, "HIGH",
       "Mid-term school break"),
    _h("MY", "Malaysia", "School Holiday (Nov)", "school_break", 11, 23, 12, 31, 38, True, "HIGH",
       "Year-end school break"),

    # ── Hong Kong (HK) ─────────────────────────────────────────────────
    _h("HK", "Hong Kong", "Chinese New Year", "cultural", 1, 25, 2, 2, 3, False, "HIGH",
       "3-day CNY — heavy short-haul outbound"),
    _h("HK", "Hong Kong", "October Golden Week", "cultural", 10, 1, 10, 7, 7, True, "HIGH",
       "Chinese tourist spillover + local holiday"),

    # ── India (IN) ──────────────────────────────────────────────────────
    _h("IN", "India", "Diwali (Festival of Lights)", "religious", 10, 20, 11, 3, 5, True, "MEDIUM",
       "Festival of lights — moderate outbound"),
    _h("IN", "India", "Summer School Break", "school_break", 4, 15, 6, 15, 60, True, "HIGH",
       "2-month school break — peak family segment"),

    # ── Indonesia (ID) ─────────────────────────────────────────────────
    _h("ID", "Indonesia", "End of Ramadan (Idul Fitri)", "religious", 3, 28, 4, 8, 5, True, "HIGH",
       "End of Ramadan — floating, largest outbound surge"),
    _h("ID", "Indonesia", "Christmas – New Year", "cultural", 12, 20, 1, 5, 14, True, "HIGH",
       "10+ day holiday — strong outbound"),

    # ── Philippines (PH) ───────────────────────────────────────────────
    _h("PH", "Philippines", "Holy Week", "religious", 3, 28, 4, 1, 4, True, "HIGH",
       "Maundy Thursday to Easter Sunday"),
    _h("PH", "Philippines", "Christmas Season", "cultural", 12, 16, 1, 6, 21, True, "HIGH",
       "Extended Christmas — 2–4 weeks off"),

    # ── Canada (CA) ─────────────────────────────────────────────────────
    _h("CA", "Canada", "Summer Break", "school_break", 6, 20, 9, 1, 70, True, "HIGH",
       "School summer break — peak long-haul travel"),
    _h("CA", "Canada", "Christmas – New Year", "cultural", 12, 20, 1, 5, 14, True, "HIGH",
       "2-week holiday block"),

    # ── United Kingdom (GB) ─────────────────────────────────────────────
    _h("GB", "United Kingdom", "Summer + Bank Holidays", "school_break", 7, 20, 9, 1, 42, True, "HIGH",
       "School summer break — main outbound season"),
    _h("GB", "United Kingdom", "Easter Bank Holiday", "religious", 3, 28, 4, 3, 4, True, "MEDIUM",
       "4-day long weekend"),
    _h("GB", "United Kingdom", "Christmas – New Year", "cultural", 12, 20, 1, 3, 14, True, "HIGH",
       "Extended Christmas holiday"),

    # ── France (FR) ─────────────────────────────────────────────────────
    _h("FR", "France", "Summer Holiday (Grandes Vacances)", "school_break", 7, 1, 8, 31, 60, True, "HIGH",
       "Full 2 months — highest outbound in Europe"),
    _h("FR", "France", "Autumn Break (Toussaint)", "school_break", 10, 19, 11, 3, 14, True, "MEDIUM",
       "2-week autumn school break"),
    _h("FR", "France", "Christmas – New Year", "cultural", 12, 20, 1, 5, 14, True, "HIGH",
       "Extended holiday season"),

    # ── Germany (DE) ────────────────────────────────────────────────────
    _h("DE", "Germany", "Summer School Holiday", "school_break", 6, 20, 9, 10, 60, True, "HIGH",
       "Varies by state (Jun–Sep) — staggered outbound"),
    _h("DE", "Germany", "Christmas Fortnight", "cultural", 12, 20, 1, 5, 14, True, "HIGH",
       "2-week Christmas break"),

    # ── Netherlands (NL) ───────────────────────────────────────────────
    _h("NL", "Netherlands", "May Holiday", "school_break", 4, 26, 5, 4, 9, True, "MEDIUM",
       "Spring school break — short trips"),
    _h("NL", "Netherlands", "Summer Holiday", "school_break", 7, 6, 8, 18, 42, True, "HIGH",
       "6-week summer break — long-haul travel peak"),

    # ── Spain (ES) ──────────────────────────────────────────────────────
    _h("ES", "Spain", "Holy Week (Semana Santa)", "religious", 3, 28, 4, 5, 7, True, "HIGH",
       "Holy Week — 1 week off"),
    _h("ES", "Spain", "August Holiday", "cultural", 8, 1, 8, 31, 30, True, "HIGH",
       "Entire month — Spain shuts down for travel"),

    # ── Italy (IT) ──────────────────────────────────────────────────────
    _h("IT", "Italy", "Mid-August Holiday (Ferragosto)", "cultural", 8, 1, 8, 20, 14, True, "HIGH",
       "Aug 15 + surrounding 2 weeks — peak outbound"),
    _h("IT", "Italy", "Christmas – New Year", "cultural", 12, 20, 1, 6, 17, True, "HIGH",
       "Extended to Epiphany (Jan 6)"),

    # ── Switzerland (CH) ───────────────────────────────────────────────
    _h("CH", "Switzerland", "Summer Holiday", "school_break", 7, 1, 8, 10, 35, True, "HIGH",
       "5-week summer break — high ADR profile"),
    _h("CH", "Switzerland", "Christmas – New Year", "cultural", 12, 20, 1, 5, 14, True, "HIGH",
       "2-week winter holiday"),

    # ── Sweden (SE) ─────────────────────────────────────────────────────
    _h("SE", "Sweden", "Summer Holiday", "school_break", 6, 10, 8, 20, 56, True, "HIGH",
       "8-week summer break — Nordics travel heavily"),
    _h("SE", "Sweden", "Christmas – New Year", "cultural", 12, 20, 1, 5, 14, True, "HIGH",
       "2-week winter holiday"),

    # ── Denmark (DK) ───────────────────────────────────────────────────
    _h("DK", "Denmark", "Summer Holiday", "school_break", 6, 25, 8, 10, 42, True, "HIGH",
       "6-week summer break"),
    _h("DK", "Denmark", "Autumn Break", "school_break", 10, 12, 10, 19, 7, True, "MEDIUM",
       "1-week autumn school break"),
    _h("DK", "Denmark", "Christmas – New Year", "cultural", 12, 20, 1, 3, 14, True, "HIGH",
       "2-week winter holiday"),

    # ── Norway (NO) ────────────────────────────────────────────────────
    _h("NO", "Norway", "Summer Holiday", "school_break", 6, 20, 8, 15, 56, True, "HIGH",
       "8-week summer break"),
    _h("NO", "Norway", "Christmas – New Year", "cultural", 12, 20, 1, 3, 14, True, "HIGH",
       "2-week winter holiday"),
]
