"""
tools/flights.py — Flight search and travel tools.

Mock backend that mirrors a real flight-search API shape.
To connect a real provider (Amadeus, Kiwi.com, etc.), replace the
internals of each function — the schemas and registry stay the same.
"""

from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

_AIRLINES: list[tuple[str, str]] = [
    ("Thai Airways",     "TG"),
    ("AirAsia",          "AK"),
    ("Bangkok Airways",  "PG"),
    ("Emirates",         "EK"),
    ("Qatar Airways",    "QR"),
    ("Singapore Air",    "SQ"),
    ("Cathay Pacific",   "CX"),
    ("Vietnam Airlines", "VN"),
    ("Scoot",            "TR"),
    ("FlyDubai",         "FZ"),
    ("Lufthansa",        "LH"),
    ("British Airways",  "BA"),
]

_AIRPORTS: dict[str, dict[str, str]] = {
    "BKK": {"name": "Suvarnabhumi",       "city": "Bangkok",      "country": "Thailand"},
    "DMK": {"name": "Don Mueang",         "city": "Bangkok",      "country": "Thailand"},
    "HKT": {"name": "Phuket Intl",        "city": "Phuket",       "country": "Thailand"},
    "CNX": {"name": "Chiang Mai Intl",    "city": "Chiang Mai",   "country": "Thailand"},
    "USM": {"name": "Koh Samui",          "city": "Koh Samui",    "country": "Thailand"},
    "SIN": {"name": "Changi",             "city": "Singapore",    "country": "Singapore"},
    "KUL": {"name": "KLIA",               "city": "Kuala Lumpur", "country": "Malaysia"},
    "DXB": {"name": "Dubai Intl",         "city": "Dubai",        "country": "UAE"},
    "DOH": {"name": "Hamad Intl",         "city": "Doha",         "country": "Qatar"},
    "LHR": {"name": "Heathrow",           "city": "London",       "country": "UK"},
    "LGW": {"name": "Gatwick",            "city": "London",       "country": "UK"},
    "CDG": {"name": "Charles de Gaulle",  "city": "Paris",        "country": "France"},
    "NRT": {"name": "Narita",             "city": "Tokyo",        "country": "Japan"},
    "HND": {"name": "Haneda",             "city": "Tokyo",        "country": "Japan"},
    "SYD": {"name": "Kingsford Smith",    "city": "Sydney",       "country": "Australia"},
    "LAX": {"name": "Los Angeles Intl",   "city": "Los Angeles",  "country": "USA"},
    "JFK": {"name": "John F. Kennedy",    "city": "New York",     "country": "USA"},
    "DEL": {"name": "Indira Gandhi Intl", "city": "New Delhi",    "country": "India"},
    "HKG": {"name": "Hong Kong Intl",     "city": "Hong Kong",    "country": "China"},
    "ICN": {"name": "Incheon",            "city": "Seoul",        "country": "South Korea"},
    "CGK": {"name": "Soekarno-Hatta",     "city": "Jakarta",      "country": "Indonesia"},
    "MNL": {"name": "Ninoy Aquino",       "city": "Manila",       "country": "Philippines"},
    "SGN": {"name": "Tan Son Nhat",       "city": "Ho Chi Minh",  "country": "Vietnam"},
    "HAN": {"name": "Noi Bai",            "city": "Hanoi",        "country": "Vietnam"},
    "RGN": {"name": "Yangon Intl",        "city": "Yangon",       "country": "Myanmar"},
}

# City-name aliases → IATA code
_CITY_TO_IATA: dict[str, str] = {
    "bangkok":        "BKK",
    "phuket":         "HKT",
    "chiang mai":     "CNX",
    "koh samui":      "USM",
    "samui":          "USM",
    "singapore":      "SIN",
    "kuala lumpur":   "KUL",
    "kl":             "KUL",
    "dubai":          "DXB",
    "doha":           "DOH",
    "london":         "LHR",
    "paris":          "CDG",
    "tokyo":          "NRT",
    "sydney":         "SYD",
    "los angeles":    "LAX",
    "new york":       "JFK",
    "new delhi":      "DEL",
    "delhi":          "DEL",
    "hong kong":      "HKG",
    "seoul":          "ICN",
    "jakarta":        "CGK",
    "manila":         "MNL",
    "ho chi minh":    "SGN",
    "saigon":         "SGN",
    "hanoi":          "HAN",
    "yangon":         "RGN",
}

_CABIN_MULTIPLIERS: dict[str, float] = {
    "economy":        1.0,
    "premium_economy": 1.8,
    "business":       3.5,
    "first":          6.0,
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _resolve_iata(query: str) -> str | None:
    """Return IATA code for a city name or pass through if already a code."""
    q = query.strip().upper()
    if q in _AIRPORTS:
        return q
    lower = query.strip().lower()
    return _CITY_TO_IATA.get(lower)


def _base_price(origin: str, destination: str) -> int:
    """Deterministic-ish base fare in USD derived from the route string."""
    seed = sum(ord(c) for c in (origin + destination))
    random.seed(seed)
    price = random.randint(80, 900)
    random.seed()          # reset global seed
    return price


def _flight_number(code: str) -> str:
    return f"{code}{random.randint(100, 999)}"


def _duration_str(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m"


# ---------------------------------------------------------------------------
# Tool: search_flights
# ---------------------------------------------------------------------------

def search_flights(
    origin:         str,
    destination:    str,
    departure_date: str,
    return_date:    str  = "",
    passengers:     int  = 1,
    cabin_class:    str  = "economy",
) -> dict[str, Any]:
    """
    Search for available flights between two cities or airports.

    Returns up to 6 flight options sorted by price, including airline,
    flight number, departure/arrival times, duration, stops, and total price.

    Args:
        origin:         Origin city name or IATA code (e.g. "Bangkok" or "BKK").
        destination:    Destination city name or IATA code (e.g. "London" or "LHR").
        departure_date: Outbound date in YYYY-MM-DD format.
        return_date:    Return date in YYYY-MM-DD format (omit for one-way).
        passengers:     Number of passengers (default 1).
        cabin_class:    "economy", "premium_economy", "business", or "first".

    Returns:
        Dict with keys:
            origin_iata, destination_iata, departure_date, cabin_class,
            passengers, trip_type ("one_way" | "round_trip"),
            flights (list of flight option dicts).
    """
    orig_iata = _resolve_iata(origin)
    dest_iata = _resolve_iata(destination)

    if not orig_iata:
        return {"error": f"Could not resolve origin airport for '{origin}'."}
    if not dest_iata:
        return {"error": f"Could not resolve destination airport for '{destination}'."}
    if orig_iata == dest_iata:
        return {"error": "Origin and destination cannot be the same airport."}

    cabin = cabin_class.lower().replace(" ", "_")
    multiplier = _CABIN_MULTIPLIERS.get(cabin, 1.0)
    base = _base_price(orig_iata, dest_iata)
    trip_type = "round_trip" if return_date else "one_way"

    try:
        dep_dt = datetime.strptime(departure_date, "%Y-%m-%d")
    except ValueError:
        return {"error": f"Invalid departure_date format '{departure_date}'. Use YYYY-MM-DD."}

    options: list[dict[str, Any]] = []
    sampled_airlines = random.sample(_AIRLINES, min(6, len(_AIRLINES)))

    for i, (airline_name, airline_code) in enumerate(sampled_airlines):
        # Vary price slightly per airline
        price_var   = random.uniform(0.85, 1.30)
        one_way_usd = round(base * multiplier * price_var)
        total_usd   = one_way_usd * passengers * (2 if trip_type == "round_trip" else 1)

        stops = 0 if i < 2 else random.choice([0, 1, 1, 2])
        base_minutes = random.randint(90, 780)
        duration_min = base_minutes + stops * random.randint(60, 120)

        dep_hour   = random.randint(0, 22)
        dep_minute = random.choice([0, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
        dep_time   = f"{dep_hour:02d}:{dep_minute:02d}"

        arr_dt     = dep_dt + timedelta(minutes=duration_min)
        arr_time   = f"{arr_dt.hour:02d}:{arr_dt.minute:02d}"
        arr_date   = arr_dt.strftime("%Y-%m-%d") if arr_dt.date() != dep_dt.date() else departure_date

        options.append({
            "rank":           i + 1,
            "airline":        airline_name,
            "flight_number":  _flight_number(airline_code),
            "origin":         orig_iata,
            "destination":    dest_iata,
            "departure_time": dep_time,
            "departure_date": departure_date,
            "arrival_time":   arr_time,
            "arrival_date":   arr_date,
            "duration":       _duration_str(duration_min),
            "stops":          stops,
            "cabin_class":    cabin,
            "price_per_pax":  f"${one_way_usd}",
            "total_price":    f"${total_usd}",
            "passengers":     passengers,
            "baggage":        "23 kg checked + 7 kg carry-on" if cabin != "economy" else "7 kg carry-on only",
            "refundable":     random.choice([True, False]),
        })

    options.sort(key=lambda x: int(x["total_price"].replace("$", "")))
    for i, opt in enumerate(options):
        opt["rank"] = i + 1

    origin_info = _AIRPORTS.get(orig_iata, {})
    dest_info   = _AIRPORTS.get(dest_iata, {})

    return {
        "origin_iata":      orig_iata,
        "origin_name":      origin_info.get("name", orig_iata),
        "origin_city":      origin_info.get("city", origin),
        "destination_iata": dest_iata,
        "destination_name": dest_info.get("name", dest_iata),
        "destination_city": dest_info.get("city", destination),
        "departure_date":   departure_date,
        "return_date":      return_date or None,
        "trip_type":        trip_type,
        "cabin_class":      cabin,
        "passengers":       passengers,
        "flights":          options,
        "results_count":    len(options),
    }


# ---------------------------------------------------------------------------
# Tool: get_flight_deals
# ---------------------------------------------------------------------------

def get_flight_deals(
    origin:      str,
    destination: str,
    month:       str = "",
) -> dict[str, Any]:
    """
    Find the cheapest travel windows and deal periods for a given route.

    Use this when the user is flexible on dates and wants to know when to
    fly to get the best price. Returns the top 5 cheapest date ranges with
    estimated round-trip prices, plus booking tips.

    Args:
        origin:      Origin city name or IATA code.
        destination: Destination city name or IATA code.
        month:       Optional month filter — name ("July") or "YYYY-MM" (e.g. "2025-08").
                     If omitted, returns deals across the next 3 months.

    Returns:
        Dict with route info, deal windows (list), and money-saving tips.
    """
    orig_iata = _resolve_iata(origin)
    dest_iata = _resolve_iata(destination)

    if not orig_iata:
        return {"error": f"Could not resolve origin airport for '{origin}'."}
    if not dest_iata:
        return {"error": f"Could not resolve destination airport for '{destination}'."}

    base = _base_price(orig_iata, dest_iata)
    today = date.today()

    # Generate 5 deal windows spread over the next 90 days
    deals: list[dict[str, Any]] = []
    for i in range(5):
        offset_days  = random.randint(i * 10 + 2, i * 10 + 14)
        window_start = today + timedelta(days=offset_days)
        window_end   = window_start + timedelta(days=random.randint(5, 10))
        discount     = random.uniform(0.65, 0.95)
        deal_price   = round(base * 2 * discount)    # round-trip

        deals.append({
            "rank":               i + 1,
            "window_start":       window_start.strftime("%d %b %Y"),
            "window_end":         window_end.strftime("%d %b %Y"),
            "estimated_rt_price": f"${deal_price}",
            "saving_vs_avg":      f"{round((1 - discount) * 100)}% cheaper",
            "best_booking_day":   random.choice(["Tuesday", "Wednesday", "Thursday"]),
            "seats_left":         random.randint(2, 12),
        })

    deals.sort(key=lambda x: int(x["estimated_rt_price"].replace("$", "")))

    tips = [
        "Book 6–8 weeks in advance for the best economy fares on this route.",
        "Tuesdays and Wednesdays are consistently the cheapest departure days.",
        "Flying out in the early morning (before 07:00) is typically 10–15% cheaper.",
        "Consider nearby airports if flexibility allows — they can cut costs further.",
        "Set a price alert so you don't miss flash sales.",
    ]

    return {
        "route":          f"{orig_iata} → {dest_iata}",
        "origin_city":    _AIRPORTS.get(orig_iata, {}).get("city", origin),
        "destination_city": _AIRPORTS.get(dest_iata, {}).get("city", destination),
        "month_filter":   month or "next 3 months",
        "currency":       "USD",
        "deal_windows":   deals,
        "money_saving_tips": tips,
    }


# ---------------------------------------------------------------------------
# Tool: get_airport_info
# ---------------------------------------------------------------------------

def get_airport_info(query: str) -> dict[str, Any]:
    """
    Look up airport details by city name or IATA code.

    Use this to resolve ambiguous city names (e.g. "London" has three major
    airports), confirm the right IATA code before searching flights, or
    provide the user with airport context.

    Args:
        query: City name (e.g. "Bangkok") or IATA code (e.g. "BKK").

    Returns:
        Dict with a list of matching airports including IATA code, full name,
        city, and country. Returns all airports for cities with multiple options.
    """
    q_upper = query.strip().upper()
    q_lower = query.strip().lower()

    results: list[dict[str, str]] = []

    # Direct IATA code match
    if q_upper in _AIRPORTS:
        info = _AIRPORTS[q_upper]
        results.append({"iata": q_upper, **info})
    else:
        # City alias match
        iata = _CITY_TO_IATA.get(q_lower)
        if iata and iata in _AIRPORTS:
            results.append({"iata": iata, **_AIRPORTS[iata]})

        # Fuzzy city match across all known airports
        for code, info in _AIRPORTS.items():
            if q_lower in info["city"].lower() and not any(r["iata"] == code for r in results):
                results.append({"iata": code, **info})

    if not results:
        return {
            "error": f"No airport found for '{query}'. "
                     "Try an IATA code (e.g. BKK) or major city name."
        }

    return {
        "query":    query,
        "matches":  results,
        "count":    len(results),
        "note":     "Multiple airports found — confirm which one with the user." if len(results) > 1 else "",
    }


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "Search for available flights between two cities or airports. "
                "Returns up to 6 options sorted by price with airline, times, "
                "duration, stops, and total cost per party."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin city name or IATA code, e.g. 'Bangkok' or 'BKK'.",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination city or IATA code, e.g. 'London' or 'LHR'.",
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "Outbound departure date in YYYY-MM-DD format.",
                    },
                    "return_date": {
                        "type": "string",
                        "description": "Return date in YYYY-MM-DD format. Omit for one-way.",
                        "default": "",
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Total number of passengers (default 1).",
                        "default": 1,
                    },
                    "cabin_class": {
                        "type": "string",
                        "enum": ["economy", "premium_economy", "business", "first"],
                        "description": "Cabin class. Default is economy.",
                        "default": "economy",
                    },
                },
                "required": ["origin", "destination", "departure_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_flight_deals",
            "description": (
                "Find the cheapest travel windows and deal periods for a route. "
                "Use when the user is flexible on dates or asks for the best "
                "time to fly, deals, or cheapest options."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin city or IATA code.",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination city or IATA code.",
                    },
                    "month": {
                        "type": "string",
                        "description": (
                            "Optional month filter: month name ('July') or "
                            "'YYYY-MM' string. Leave blank for next 3 months."
                        ),
                        "default": "",
                    },
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_airport_info",
            "description": (
                "Look up airport details by city name or IATA code. "
                "Use to resolve ambiguous city names, confirm IATA codes, "
                "or find all airports serving a city (e.g. London has LHR, LGW, STN)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "City name (e.g. 'Bangkok') or IATA code (e.g. 'BKK').",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

REGISTRY: dict[str, Any] = {
    "search_flights":    search_flights,
    "get_flight_deals":  get_flight_deals,
    "get_airport_info":  get_airport_info,
}
