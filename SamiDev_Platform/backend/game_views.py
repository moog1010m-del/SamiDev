"""The browser must never receive a private, server-side card checkpoint."""
from copy import deepcopy
from games import game_id
from store import StoreError


def client_state(payload: dict, settings: dict, seat: int) -> dict:
    if game_id(settings) != "crazy8":
        return payload
    snapshot = payload.get("snapshot")
    views = snapshot.get("_samidev_clientViews") if isinstance(snapshot, dict) else None
    view = views.get(str(seat)) if isinstance(views, dict) else None
    if not isinstance(view, dict):
        # Fail closed on old/missing checkpoints; a full server snapshot is never
        # an acceptable fallback for a player or spectator.
        raise StoreError("PRIVATE_STATE_UNAVAILABLE", "تعذر استعادة حالة الأوراق، حاول الاتصال مجددًا")
    result = dict(payload)
    result["snapshot"] = deepcopy(view)
    return result
