
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
import json
import re

@dataclass
class Outcome:
    key: str
    label: str
    price: Optional[float]
    line: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Market:
    name: str
    spec: str
    outcomes: List[Outcome]
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Event:
    sport: str
    event_id: str
    league: Optional[str]
    start_time_utc: Optional[str]
    home: Optional[str]
    away: Optional[str]
    markets: List[Market]
    raw: Dict[str, Any] = field(default_factory=dict)

def _dig(d: Dict[str, Any], *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            lk = k.lower() if isinstance(k, str) else k
            found = None
            for ck in cur.keys():
                if isinstance(ck, str) and ck.lower() == lk:
                    found = ck; break
            if found is None:
                return default
            cur = cur[found]
        elif isinstance(cur, list):
            try:
                cur = cur[k]
            except Exception:
                return default
        else:
            return default
    return cur

def parse_decimal(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            if re.fullmatch(r"[+-]?\d+", s):
                american = int(s)
                if american > 0:
                    return round(1 + american / 100.0, 4)
                else:
                    return round(1 + 100.0 / abs(american), 4)
            return None
    return None

def parse_iso8601(dt_str: str) -> Optional[str]:
    if not dt_str or not isinstance(dt_str, str):
        return None
    s = dt_str.strip()
    fmts = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z","").replace("z",""))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None

def join_date_time(date_str: Optional[str], time_str: Optional[str]) -> Optional[str]:
    if date_str and time_str:
        s = f"{date_str.strip()} {time_str.strip()}"
        return parse_iso8601(s)
    if date_str and not time_str:
        return parse_iso8601(date_str)
    if time_str and not date_str:
        return parse_iso8601(time_str)
    return None

TEAM_FIELD_CANDIDATES = [
    ("localteam", "visitorteam"),
    ("home_team", "away_team"),
    ("home", "away"),
    ("team1", "team2"),
    ("player_1", "player_2"),
    ("p1", "p2"),
    ("fighter_1", "fighter_2"),
]

def extract_teams(ev: Dict[str, Any]):
    for a,b in TEAM_FIELD_CANDIDATES:
        ha = _dig(ev, a)
        aw = _dig(ev, b)
        if ha or aw:
            if isinstance(ha, dict):
                ha = _dig(ha, "name", default=ha.get("team") if isinstance(ha, dict) else ha)
            if isinstance(aw, dict):
                aw = _dig(aw, "name", default=aw.get("team") if isinstance(aw, dict) else aw)
            return (str(ha).strip() if ha else None, str(aw).strip() if aw else None)
    ha = _dig(ev, "home")
    aw = _dig(ev, "away")
    return (str(ha).strip() if ha else None, str(aw).strip() if aw else None)

def extract_league(ev: Dict[str, Any]) -> Optional[str]:
    cand = _dig(ev, "league") or _dig(ev, "competition") or _dig(ev, "tournament")
    if isinstance(cand, dict):
        return _dig(cand, "name") or _dig(cand, "league_name")
    return str(cand).strip() if cand else None

def extract_event_id(ev: Dict[str, Any]) -> str:
    for k in ["id", "match_id", "event_id", "game_id", "fixture_id"]:
        v = _dig(ev, k)
        if v is not None:
            return str(v)
    home, away = extract_teams(ev)
    start = extract_start_time(ev)
    base = f"{home or ''}-{away or ''}-{start or ''}"
    return re.sub(r"[^a-zA-Z0-9]+", "_", base) or str(abs(hash(json.dumps(ev, sort_keys=True))))

def extract_start_time(ev: Dict[str, Any]) -> Optional[str]:
    for k in ["start_time", "event_time", "kickoff", "datetime", "match_time", "starts_at"]:
        iso = parse_iso8601(str(_dig(ev, k) or ""))
        if iso:
            return iso
    date = _dig(ev, "date") or _dig(ev, "match_date")
    time = _dig(ev, "time") or _dig(ev, "match_time")
    iso = join_date_time(date, time)
    return iso

CANONICAL_MARKETS = {
    "match_result", "asian_handicap", "over_under",
    "first_half_winner", "first_quarter_winner", "highest_scoring_quarter", "odd_even_including_ot",
    "home_away", "set_betting", "games_over_under", "over_under_first_set", "first_set",
    "asian_handicap_sets", "asian_handicap_games", "tie_break_first_set", "second_set",
    "win_one_set_player1", "win_one_set_player2",
    "correct_score", "odd_even_first_set",
}

MARKET_ALIASES = {
    "1x2": "match_result",
    "moneyline_3way": "match_result",
    "ml_3way": "match_result",
    "ml": "home_away",
    "win": "home_away",
    "winner": "home_away",
    "match_winner": "home_away",
    "totals": "over_under",
    "over/under": "over_under",
    "ou": "over_under",
    "asian_handicap": "asian_handicap",
    "ah": "asian_handicap",
    "handicap": "asian_handicap",
    "fh_winner": "first_half_winner",
    "1st_half_winner": "first_half_winner",
    "first_quarter_winner": "first_quarter_winner",
    "highest_scoring_quarter": "highest_scoring_quarter",
    "odd_even": "odd_even_including_ot",
    "odd_even_incl_ot": "odd_even_including_ot",
    "correct_score": "correct_score",
    "first_set_winner": "first_set",
    "set_betting": "set_betting",
    "games_ou": "games_over_under",
    "ou_first_set": "over_under_first_set",
    "asian_handicap_sets": "asian_handicap_sets",
    "asian_handicap_games": "asian_handicap_games",
    "tie_break_first_set": "tie_break_first_set",
    "second_set_winner": "second_set",
    "win_one_set_p1": "win_one_set_player1",
    "win_one_set_p2": "win_one_set_player2",
}

OUTCOME_ALIASES = {
    "home": {"home", "h", "1", "local", "team1", "p1", "player_1", "fighter_1"},
    "away": {"away", "a", "2", "visitor", "team2", "p2", "player_2", "fighter_2"},
    "draw": {"draw", "x", "d", "tie"},
    "over": {"over", "o"},
    "under": {"under", "u"},
    "odd": {"odd"},
    "even": {"even"},
    "yes": {"yes", "y"},
    "no": {"no", "n"},
}

def normalize_market_name(name: str) -> Optional[str]:
    if not name:
        return None
    key = name.strip().lower().replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "_", key)
    if key in CANONICAL_MARKETS:
        return key
    return MARKET_ALIASES.get(key, key if key in CANONICAL_MARKETS else None)

def normalize_outcome_key(label: str) -> Optional[str]:
    if label is None:
        return None
    raw = str(label).strip().lower()
    raw = re.sub(r"\s+", "", raw)
    for canon, alset in OUTCOME_ALIASES.items():
        if raw in alset:
            return canon
    if raw == "1":
        return "home"
    if raw in {"x", "d"}:
        return "draw"
    if raw == "2":
        return "away"
    return None

def market_spec_for(canonical: str) -> str:
    if canonical == "match_result":
        return "3way"
    if canonical in {"home_away", "first_half_winner", "first_quarter_winner", "highest_scoring_quarter",
                     "odd_even_including_ot", "first_set", "second_set",
                     "win_one_set_player1", "win_one_set_player2"}:
        return "2way"
    if canonical in {"over_under", "games_over_under", "over_under_first_set"}:
        return "totals"
    if canonical in {"asian_handicap", "asian_handicap_sets", "asian_handicap_games"}:
        return "handicap"
    if canonical in {"correct_score", "set_betting"}:
        return "grid"
    if canonical in {"tie_break_first_set"}:
        return "yes_no"
    return "unknown"

from typing import List as _List

def parse_outcomes_generic(market_payload: Dict[str, Any]) -> _List[Outcome]:
    outcomes: _List[Outcome] = []
    for list_key, price_keys in [
        ("outcomes", ["price","odds","decimal","value"]),
        ("selections", ["price","odds","decimal","value"]),
    ]:
        seq = _dig(market_payload, list_key)
        if isinstance(seq, list):
            for it in seq:
                label = _dig(it, "name") or _dig(it, "label") or _dig(it, "key") or _dig(it, "selection")
                price_val = None
                for pk in price_keys:
                    pv = _dig(it, pk)
                    if pv is not None:
                        price_val = pv; break
                line = _dig(it, "line") or _dig(it, "handicap") or _dig(it, "total")
                outcomes.append(Outcome(
                    key = normalize_outcome_key(label) or (str(label).lower() if label else "unknown"),
                    label = str(label) if label is not None else "unknown",
                    price = parse_decimal(price_val),
                    line = parse_decimal(line),
                    raw = it if isinstance(it, dict) else {"value": it}
                ))
            if outcomes:
                return outcomes

    prices = _dig(market_payload, "prices") or _dig(market_payload, "odds") or _dig(market_payload, "lines")
    if isinstance(prices, dict):
        for label, price_val in prices.items():
            outcomes.append(Outcome(
                key = normalize_outcome_key(str(label)) or str(label),
                label = str(label),
                price = parse_decimal(price_val),
                raw = {"label":label, "price":price_val}
            ))
        if outcomes:
            return outcomes

    keys = list(market_payload.keys())
    for k in keys:
        if isinstance(k, str) and k.lower() in ["home","away","draw","over","under","odd","even"]:
            outcomes.append(Outcome(
                key = normalize_outcome_key(k) or k.lower(),
                label = k,
                price = parse_decimal(market_payload[k]),
                raw = {"label":k, "price":market_payload[k]}
            ))
    return outcomes

def parse_totals(market_payload: Dict[str, Any]) -> _List[Outcome]:
    outcomes = parse_outcomes_generic(market_payload)
    fixed: _List[Outcome] = []
    for oc in outcomes:
        k = normalize_outcome_key(oc.key) or normalize_outcome_key(oc.label) or oc.key
        ln = oc.line
        if ln is None:
            ln = parse_decimal(_dig(market_payload, "line") or _dig(market_payload, "total") or _dig(market_payload, "points"))
        fixed.append(Outcome(key=k, label=oc.label, price=oc.price, line=ln, raw=oc.raw))
    return fixed

def parse_handicap(market_payload: Dict[str, Any]) -> _List[Outcome]:
    outcomes = parse_outcomes_generic(market_payload)
    fixed: _List[Outcome] = []
    for oc in outcomes:
        ln = oc.line
        if ln is None:
            ln = parse_decimal(_dig(market_payload, "handicap") or _dig(market_payload, "line"))
        fixed.append(Outcome(key=oc.key, label=oc.label, price=oc.price, line=ln, raw=oc.raw))
    return fixed

def parse_grid(market_payload: Dict[str, Any]) -> _List[Outcome]:
    outcomes = []
    seq = _dig(market_payload, "outcomes") or _dig(market_payload, "selections")
    if isinstance(seq, list):
        for it in seq:
            label = _dig(it, "name") or _dig(it, "label") or _dig(it, "score")
            price_val = _dig(it, "price") or _dig(it, "odds")
            outcomes.append(Outcome(
                key=str(label).lower().replace(" ", "_"),
                label=str(label),
                price=parse_decimal(price_val),
                raw=it
            ))
    else:
        outcomes = parse_outcomes_generic(market_payload)
    return outcomes

def parse_yes_no(market_payload: Dict[str, Any]) -> _List[Outcome]:
    outcomes = parse_outcomes_generic(market_payload)
    if not outcomes:
        outcomes = [
            Outcome(key="yes", label="Yes", price=parse_decimal(_dig(market_payload, "yes"))),
            Outcome(key="no", label="No", price=parse_decimal(_dig(market_payload, "no"))),
        ]
    return outcomes

MARKET_PARSERS = {
    "3way": parse_outcomes_generic,
    "2way": parse_outcomes_generic,
    "totals": parse_totals,
    "handicap": parse_handicap,
    "grid": parse_grid,
    "yes_no": parse_yes_no,
    "unknown": parse_outcomes_generic,
}

SPORT_MARKETS = {
    "soccer": ["match_result", "asian_handicap", "over_under"],
    "basketball": ["match_result", "first_half_winner", "first_quarter_winner", "highest_scoring_quarter", "odd_even_including_ot"],
    "tennis": ["home_away", "set_betting", "games_over_under", "over_under_first_set", "first_set", "asian_handicap_sets", "asian_handicap_games", "tie_break_first_set", "second_set", "win_one_set_player1", "win_one_set_player2"],
    "table_tennis": ["home_away", "first_set", "set_betting"],
    "darts": ["match_result"],
    "volleyball": ["home_away", "correct_score", "odd_even_first_set", "over_under_first_set", "first_set"],
    "handball": ["match_result"],
    "baseball": ["match_result", "correct_score", "odd_even_including_ot"],
    "cricket": ["home_away", "most_sixes", "most_fours", "most_run_outs"],
    "hockey": ["match_result", "over_under", "first_half_winner"],
    "futsal": ["match_result", "over_under"],
    "boxing": ["match_result", "over_under"],
    "mma": ["match_result", "over_under"],
    "esports": ["match_result"],
    "football": ["match_result", "over_under", "first_half_winner"],
    "rugby": ["match_result", "over_under", "asian_handicap"],
    "rugbyleague": ["match_result", "over_under", "asian_handicap"],
}

def parse_events_from_feed(data: Union[Dict[str, Any], List[Dict[str, Any]]]):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["events", "matches", "fixtures", "data", "results", "games"]:
            seq = _dig(data, key)
            if isinstance(seq, list):
                return seq
        if any(_dig(data, k) is not None for k in ["id","match_id","event_id","fixture_id"]):
            return [data]
    return []

def parse_event_generic(ev: Dict[str, Any], sport: str) -> Event:
    event_id = extract_event_id(ev)
    league = extract_league(ev)
    start_time = extract_start_time(ev)
    home, away = extract_teams(ev)

    markets_payload = (
        _dig(ev, "markets") or _dig(ev, "odds") or _dig(ev, "betting") or
        _dig(ev, "lines") or _dig(ev, "books")
    )

    normalized_markets: List[Market] = []

    def iter_market_items(payload):
        items = []
        if isinstance(payload, list):
            for m in payload:
                mname = _dig(m, "name") or _dig(m, "market") or _dig(m, "key") or _dig(m, "type")
                if mname:
                    items.append((str(mname), m))
        elif isinstance(payload, dict):
            for k, v in payload.items():
                items.append((str(k), v if isinstance(v, dict) else {"values": v}))
        return items

    if markets_payload is not None:
        for raw_name, mp in iter_market_items(markets_payload):
            canonical = normalize_market_name(raw_name)
            if not canonical:
                continue
            if sport in SPORT_MARKETS and canonical not in SPORT_MARKETS[sport]:
                continue
            spec = market_spec_for(canonical)
            parser = MARKET_PARSERS.get(spec, parse_outcomes_generic)
            try:
                outcomes = parser(mp if isinstance(mp, dict) else {"values": mp})
            except Exception:
                outcomes = []
            if outcomes:
                normalized_markets.append(Market(
                    name=canonical,
                    spec=spec,
                    outcomes=outcomes,
                    raw=mp if isinstance(mp, dict) else {"values": mp}
                ))

    return Event(
        sport = sport,
        event_id = event_id,
        league = league,
        start_time_utc = start_time,
        home = home,
        away = away,
        markets = normalized_markets,
        raw = ev
    )

def parse_by_sport(sport: str, json_payload: Union[Dict[str, Any], List[Any]]):
    events = parse_events_from_feed(json_payload)
    parsed: List[Event] = []
    for ev in events:
        try:
            parsed.append(parse_event_generic(ev, sport))
        except Exception:
            continue
    return [asdict(e) for e in parsed]

def parse_soccer(data): return parse_by_sport("soccer", data)
def parse_basketball(data): return parse_by_sport("basketball", data)
def parse_tennis(data): return parse_by_sport("tennis", data)
def parse_table_tennis(data): return parse_by_sport("table_tennis", data)
def parse_darts(data): return parse_by_sport("darts", data)
def parse_volleyball(data): return parse_by_sport("volleyball", data)
def parse_handball(data): return parse_by_sport("handball", data)
def parse_baseball(data): return parse_by_sport("baseball", data)
def parse_cricket(data): return parse_by_sport("cricket", data)
def parse_hockey(data): return parse_by_sport("hockey", data)
def parse_futsal(data): return parse_by_sport("futsal", data)
def parse_boxing(data): return parse_by_sport("boxing", data)
def parse_mma(data): return parse_by_sport("mma", data)
def parse_esports(data): return parse_by_sport("esports", data)
def parse_football(data): return parse_by_sport("football", data)
def parse_rugby(data): return parse_by_sport("rugby", data)
def parse_rugbyleague(data): return parse_by_sport("rugbyleague", data)
