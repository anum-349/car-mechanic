"""Writes scamcheck fixture  (run: python scripts/build_scam_fixture.py)
Adjust the app label if your model is not scamcheck.scamcheck."""
import json

TS, USER, CITY = "2026-10-30T12:00:00Z", 6, "Lahore"
MODEL = "scamshield.scamcheck"          # <- change to your app label

# pk: (name, total_min, total_max, proof hint)   totals = parts + labour from the cause fixture
C = {
 300101: ("Weak or dead battery", 12000, 31000), 300102: ("Loose or corroded battery terminals", 500, 2000),
 300103: ("Faulty starter motor or solenoid", 12000, 40000), 300104: ("Failed fuel pump or fuel pump relay", 10000, 46000),
 300105: ("Immobiliser or key fault", 4000, 29000),
 300106: ("Low coolant or a coolant leak", 1000, 11000), 300107: ("Stuck thermostat", 3000, 9000),
 300108: ("Radiator fan or fan relay failure", 4500, 19000), 300109: ("Failing water pump", 9000, 29000),
 300110: ("Head gasket leak", 33000, 90000),
 300111: ("Warped brake discs", 8000, 30000), 300112: ("Worn brake pads", 4000, 15000),
 300113: ("Seized brake caliper", 7000, 25000), 300114: ("Brake fluid leak or air in the brake lines", 4000, 21000),
 300115: ("Low refrigerant or a leak in the AC system", 3000, 11000), 300116: ("Compressor or compressor clutch failure", 19000, 59000),
 300117: ("Condenser fan not working", 4500, 15500), 300118: ("Blocked cabin filter or weak blower", 500, 5000),
 300119: ("Blown AC fuse or relay", 100, 2500),
 300120: ("Old or worn-out battery", 12000, 31000), 300121: ("Faulty alternator", 12000, 46000),
 300122: ("Parasitic drain from a device left on", 1500, 8000), 300123: ("Loose or corroded battery terminals", 500, 2000),
}

# problem: (label, ranked candidate pks, [(kind, claimed_pk, claim_text, price)])
SCENARIOS = [
 ("Engine won't start", [300101, 300103, 300102, 300104, 300105], [
   ("plausible", 300101, "Battery is finished, needs a new one", 22000),
   ("doubtful", 300104, "Fuel pump has failed", 25000),
   ("suspicious", 300104, "Fuel pump and wiring both gone", 120000),
   ("limited", None, "Mechanic said the electrical system is damaged", 35000)]),
 ("Engine overheating", [300108, 300106, 300107, 300109, 300110], [
   ("plausible", 300108, "Radiator fan relay is dead", 9000),
   ("doubtful", 300110, "Head gasket has blown", 60000),
   ("suspicious", 300109, "Water pump and radiator both need replacing", 80000),
   ("limited", None, "Mechanic said the engine is cooking itself", 50000)]),
 ("Brake noise or shaking", [300112, 300111, 300113, 300114], [
   ("plausible", 300112, "Front brake pads are worn", 7000),
   ("doubtful", 300111, "Discs are warped and need replacing", 20000),
   ("suspicious", 300113, "Both calipers seized", 70000),
   ("limited", None, "Mechanic said the whole brake system needs doing", 45000)]),
 ("AC not cooling", [300115, 300116, 300117, 300118, 300119], [
   ("plausible", 300115, "AC gas is low, needs refill and leak seal", 6000),
   ("doubtful", 300116, "Compressor has failed", 30000),
   ("suspicious", 300116, "Compressor and condenser both need replacing", 150000),
   ("limited", None, "Mechanic said the AC system is gone", 40000)]),
 ("Battery keeps draining", [300122, 300120, 300121, 300123], [
   ("plausible", 300122, "Something is draining the battery overnight", 4000),
   ("doubtful", 300121, "Alternator is faulty", 30000),
   ("suspicious", 300121, "Alternator and battery both need replacing", 120000),
   ("limited", None, "Mechanic said the wiring is bad", 30000)]),
]
SCORE = {"plausible": "0.85", "doubtful": "0.50", "suspicious": "0.15", "limited": "0.50"}
VERDICT = {"plausible": "plausible", "doubtful": "doubtful", "suspicious": "suspicious", "limited": "doubtful"}

def reasons(kind, ranked, claimed, price):
    if kind == "limited":
        return ["No cause was selected, so the quote cannot be compared with a specific repair."]
    name, lo, hi = C[claimed]
    out = []
    if claimed == ranked[0]:
        out.append("The named cause is the top likely cause from your symptoms.")
    else:
        out.append(f"Your symptoms rank {C[ranked[0]][0]} higher than {name}.")
    if price > hi:
        out.append(f"The quote is {price / hi:.1f}x the top of the usual range (PKR {lo:,} to {hi:,}).")
    elif price < lo:
        out.append(f"The quote is below the usual range (PKR {lo:,} to {hi:,}); check what is included.")
    else:
        out.append(f"The quote is inside the usual range (PKR {lo:,} to {hi:,}).")
    return out

out, pk = [], 400001
for label, ranked, rows in SCENARIOS:
    cands = [{"cause": p, "name": C[p][0], "rank": i} for i, p in enumerate(ranked, 1)]
    for kind, claimed, text, price in rows:
        limited = kind == "limited"
        cost = {} if limited else {"city": CITY, "min": C[claimed][1], "max": C[claimed][2], "currency": "PKR"}
        out.append({"model": MODEL, "pk": pk, "fields": {
            "user": USER, "session": None, "claimed_cause": claimed, "claim_text": text,
            "quoted_price": price, "plausibility": SCORE[kind], "verdict": VERDICT[kind],
            "city": CITY, "price_basis": "unavailable" if limited else "city", "cost": cost,
            "reasons": reasons(kind, ranked, claimed, price),
            "proof_suggestions": ["Ask to see the old part.", "Ask for the test result or measurement that confirms the fault.",
                                  "Ask for an itemised quote (parts and labour)."],
            "candidate_causes": cands, "limited": limited, "created_at": TS}})
        pk += 1

with open("./fixtures/scam_checks.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print(len(out), "scam checks written")