"""Canonical game identifiers and public settings for the shared platform."""
from typing import Any

GAMES = {
    "pool": {"id":"pool", "name":"البلياردو", "title":"SamiDev Pool", "entry":"/games/pool/index.html", "main":"games/pool/main.js"},
    "carrom": {"id":"carrom", "name":"الكيرم", "title":"SamiDev Carrom", "entry":"/index.html", "main":"main.js"},
    "tablesoccer": {"id":"tablesoccer", "name":"كرة الطاولة", "title":"SamiDev Table Soccer", "entry":"/games/tablesoccer/index.html", "main":"games/tablesoccer/main.js"},
    "crazy8": {"id":"crazy8", "name":"بلازر أونو", "title":"Plazr Uno", "entry":"/games/crazy8/index.html", "main":"games/crazy8/main.js"},
}

def game_id(settings: Any) -> str:
    return str(settings.get("gameId") or "carrom") if isinstance(settings, dict) else "carrom"


def game_capacity(settings: dict[str, Any]) -> int:
    if game_id(settings) == "pool": return (2,4,4,2,4,4,3,2)[settings.get("gameType",0)]
    if game_id(settings) == "crazy8":
        return (2, 3, 4, 6, 4)[settings["seats"]]
    return 2 if settings["players"] == 0 else 4
