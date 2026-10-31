"""Explainable comparison of a repair quote with diagnosis and visible prices."""
from decimal import Decimal

from django.conf import settings

from diagnosis.engine import rank_causes
from knowledge.models import RepairCost

from .models import ScamCheck

GENERIC_PROOF_SUGGESTIONS = [
    "Ask which part is worn and ask to be shown it.",
    "Ask for the old part back.",
]


def find_cost(cause, city):
    """Return the visible local/fallback cost row and its basis label."""
    if cause is None:
        return None, "unavailable"
    costs = RepairCost.objects.visible().filter(cause=cause)
    local = costs.filter(city__iexact=(city or "")).first() if city else None
    if local:
        return local, "local_city"
    fallback = costs.order_by("id").first()
    return (fallback, "other_city") if fallback else (None, "unavailable")


def _price_score(price, cost):
    if cost is None:
        return Decimal("0.5"), None
    low = Decimal(cost.parts_min + cost.labour_min)
    high = Decimal(cost.parts_max + cost.labour_max)
    quoted = Decimal(price)
    if quoted > high * Decimal("1.5"):
        return Decimal("0.2"), "high"
    if quoted > high:
        return Decimal("0.6"), "above"
    if quoted < low * Decimal("0.5"):
        return Decimal("0.9"), "cheap"
    if quoted < low:
        return Decimal("0.9"), "below"
    return Decimal("1.0"), "range"


def cost_payload(cost, basis):
    if cost is None:
        return {}
    return {
        "city": cost.city,
        "parts_min": cost.parts_min,
        "parts_max": cost.parts_max,
        "labour_min": cost.labour_min,
        "labour_max": cost.labour_max,
        "total_min": cost.parts_min + cost.labour_min,
        "total_max": cost.parts_max + cost.labour_max,
        "last_verified": cost.last_verified.isoformat() if cost.last_verified else None,
        "price_basis": basis,
    }


def evaluate(session, claimed_cause, quoted_price, city):
    """Return (plausibility, verdict, reasons, proof_suggestions)."""
    reasons = []
    candidates = rank_causes(session, top=None) if session is not None else []
    confidence = next((Decimal(str(item["confidence"])) for item in candidates
                       if item["cause"].pk == getattr(claimed_cause, "pk", None)), None)
    is_candidate = confidence is not None
    probability = confidence if is_candidate else Decimal("0")
    if claimed_cause is None:
        reasons.append("Choose a cause from the diagnosis list before comparing this quote.")
    elif not is_candidate:
        reasons.append("This cause is not a candidate for this car and category; it is unlikely based on your symptoms.")
    elif probability < Decimal("0.15"):
        reasons.append("This cause is unlikely based on your symptoms.")
    else:
        reasons.append("This cause is consistent with your diagnosis symptoms.")

    cost, _basis = find_cost(claimed_cause, city)
    price_score, price_status = _price_score(quoted_price, cost)
    if cost is None:
        reasons.append("No usual cost range is available; ask for proof of the quoted amount.")
    else:
        low = cost.parts_min + cost.labour_min
        high = cost.parts_max + cost.labour_max
        if price_status in ("high", "above"):
            reasons.append(f"The quote is higher than the usual range (PKR {low:,}–{high:,}).")
        elif price_status == "cheap":
            reasons.append(f"The quote is unusually cheap (usual range PKR {low:,}–{high:,}); ask about part quality.")
        elif price_status == "below":
            reasons.append(f"The quote is below the usual range (PKR {low:,}–{high:,}).")
        else:
            reasons.append(f"The quote is within the usual range (PKR {low:,}–{high:,}).")

    plausibility = (Decimal("0.6") * min(probability * 2, Decimal("1"))
                    + Decimal("0.4") * price_score)
    plausibility = plausibility.quantize(Decimal("0.01"))
    if plausibility >= Decimal(str(settings.SCAMSHIELD_PLAUSIBLE_THRESHOLD)):
        verdict = ScamCheck.Verdict.PLAUSIBLE
    elif plausibility >= Decimal(str(settings.SCAMSHIELD_DOUBTFUL_THRESHOLD)):
        verdict = ScamCheck.Verdict.DOUBTFUL
    else:
        verdict = ScamCheck.Verdict.SUSPICIOUS
    if cost is None and verdict == ScamCheck.Verdict.SUSPICIOUS:
        verdict = ScamCheck.Verdict.DOUBTFUL

    hint = (claimed_cause.proof_hint.strip() if claimed_cause is not None else "")
    proof_suggestions = [line.strip() for line in hint.splitlines() if line.strip()]
    if not proof_suggestions:
        proof_suggestions = list(GENERIC_PROOF_SUGGESTIONS)
    if any("ask for proof" in reason.lower() for reason in reasons):
        pass
    else:
        reasons.append("Ask for proof of the diagnosis and the quoted parts and labour.")
    return plausibility, verdict, reasons, proof_suggestions
