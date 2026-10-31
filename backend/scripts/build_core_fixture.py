"""Writes knowledge/fixtures/core_problems.json  (run: python scripts/build_core_fixture.py)"""
import json

TS, USER = "2026-10-30T12:00:00Z", 6
W = {"always": "0.90", "often": "0.70", "sometimes": "0.40", "rarely": "0.10"}
GOV = {"status": "published", "is_dummy": False, "version": 1, "created_by": USER,
       "approved_by": USER, "created_at": TS, "updated_at": TS}
YN = [("Yes", "Haan", "confirms", None), ("No", "Nahi", "denies", None)]

# symptom: (pk, key, en, roman, safety_critical)
# cause:   (alias, name, system, prior, severity, safe_to_drive, description,
#           self_check_steps, tools, difficulty, (parts_min, parts_max, labour_min, labour_max))
# link:    (cause_alias, symptom_pk, strength)
# question:(symptom_pk, en, roman, triage_order, options)   options=None -> yes/no
#          triage options: [(label, roman, implies_symptom_pk)]
PROBLEMS = [
 dict(category=9002,
  symptoms=[
   (300001, "clicking-only-when-turning-key", "Only a clicking sound when turning the key", "Chaabi ghumane par sirf click ki awaaz aati hai", False),
   (300002, "dashboard-lights-dim-when-cranking", "Dashboard lights dim or go out when turning the key", "Chaabi ghumane par dashboard ki lights dheemi ya band ho jati hain", False),
   (300003, "nothing-happens-when-turning-key", "Nothing happens at all when turning the key", "Chaabi ghumane par bilkul kuch nahi hota", False),
   (300004, "fuel-pump-silent-ignition-on", "Fuel pump is silent when the ignition is switched on", "Ignition on karne par fuel pump ki halki awaaz nahi aati", False),
   (300005, "security-light-flashing", "Security or key light keeps flashing on the dashboard", "Dashboard par security ya chaabi ki light jhapakti rehti hai", False)],
  causes=[
   ("batt", "Weak or dead battery", "electrical", 0.35, "medium", True, "The battery cannot supply enough current to crank the engine.", "Try the headlights: if they are dim or die when you turn the key, the battery is weak. A jump-start that works confirms it.", "Jumper cables", "easy", (12000, 30000, 0, 1000)),
   ("term", "Loose or corroded battery terminals", "electrical", 0.15, "low", True, "Poor contact at the terminals blocks current even with a good battery.", "With the car off, check that both terminals are tight and free of white or green crust.", "Spanner, wire brush", "easy", (0, 500, 500, 1500)),
   ("starter", "Faulty starter motor or solenoid", "electrical", 0.20, "medium", True, "The starter does not turn the engine even though the battery is good.", "If lights stay bright but you only hear one loud click, the starter is the likely cause.", "None", "medium", (10000, 35000, 2000, 5000)),
   ("fuelpump", "Failed fuel pump or fuel pump relay", "fuel", 0.20, "medium", True, "The engine cranks but no fuel reaches it.", "Switch the ignition on and listen near the rear seat for a 2 second hum. Silence points to the pump, relay or fuse.", "None", "medium", (8000, 40000, 2000, 6000)),
   ("immo", "Immobiliser or key fault", "electrical", 0.10, "medium", True, "The car does not recognise the key and blocks starting.", "Try the spare key and check whether the security light flashes.", "Spare key", "easy", (3000, 25000, 1000, 4000))],
  links=[("batt", 102125, "often"), ("batt", 300002, "always"), ("batt", 300001, "often"), ("batt", 300003, "sometimes"), ("batt", 100172, "often"), ("batt", 101715, "sometimes"),
         ("term", 102125, "often"), ("term", 300001, "often"), ("term", 300002, "often"), ("term", 300003, "often"), ("term", 101715, "rarely"),
         ("starter", 102125, "often"), ("starter", 300001, "always"), ("starter", 300003, "often"), ("starter", 300002, "rarely"),
         ("fuelpump", 102125, "often"), ("fuelpump", 100781, "always"), ("fuelpump", 300004, "always"), ("fuelpump", 101715, "sometimes"),
         ("immo", 102125, "often"), ("immo", 100781, "often"), ("immo", 300005, "always")],
  questions=[
   (102125, "When you turn the key, what happens?", "Chaabi ghumane par kya hota hai?", 1,
    [("Nothing at all", "Kuch bhi nahi hota", 300003), ("Only a click or dim lights", "Sirf click ya dheemi lights", 300001), ("The engine cranks but will not start", "Engine ghoomta hai lekin start nahi hota", 100781)]),
   (300002, "Do the dashboard lights dim or go out when you turn the key?", "Kya chaabi ghumane par dashboard ki lights dheemi ya band ho jati hain?", 0, None),
   (300001, "Do you hear only a clicking sound when you turn the key?", "Kya chaabi ghumane par sirf click ki awaaz aati hai?", 0, None),
   (300003, "Does nothing at all happen when you turn the key?", "Kya chaabi ghumane par bilkul kuch nahi hota?", 0, None),
   (100781, "Does the engine turn over (crank) but never catch and run?", "Kya engine ghoomta hai lekin kabhi chalu nahi hota?", 0, None),
   (300004, "With the ignition on, is the fuel pump silent (no short hum for about 2 seconds)?", "Ignition on karne par kya fuel pump ki halki awaaz nahi aati?", 0, None),
   (300005, "Is a security or key light flashing on the dashboard?", "Kya dashboard par security ya chaabi ki light jhapak rahi hai?", 0, None),
   (101715, "Does the engine crank for much longer than usual before it starts?", "Kya engine start hone se pehle normal se zyada der ghoomta hai?", 0, None),
   (100172, "Has the battery been weak lately, especially on cold mornings?", "Kya battery haal hi mein kamzor rahi hai, khaas tor par thandi subah mein?", 0, None)]),

 dict(category=9003,
  symptoms=[
   (300010, "temperature-gauge-climbs-high", "Temperature gauge climbs above the middle", "Temperature gauge beech se upar chala jata hai", False),
   (300011, "steam-from-under-bonnet", "Steam or smoke coming from under the bonnet", "Bonnet ke neeche se bhaap ya dhuan nikalta hai", True),
   (300012, "heater-cold-engine-hot", "Heater blows cold air while the engine is hot", "Engine garam hone par bhi heater thandi hawa deta hai", False)],
  causes=[
   ("cool", "Low coolant or a coolant leak", "cooling", 0.30, "high", True, "Not enough coolant is left to carry heat away from the engine.", "When the engine is completely cold, check the coolant tank level and look under the car for drips.", "Torch", "easy", (500, 8000, 500, 3000)),
   ("thermo", "Stuck thermostat", "cooling", 0.15, "medium", True, "The thermostat stays closed and traps hot coolant in the engine.", "With the engine hot, the upper radiator hose is hot but the lower hose stays cold.", "None", "medium", (1500, 5000, 1500, 4000)),
   ("fan", "Radiator fan or fan relay failure", "cooling", 0.20, "medium", True, "The fan does not blow air through the radiator when the car is stopped.", "Let the engine warm up at idle: the fan should start within a few minutes. If it never does, check the fuse and relay.", "None", "medium", (3000, 15000, 1500, 4000)),
   ("pump", "Failing water pump", "cooling", 0.10, "high", False, "The pump does not circulate coolant properly.", "Look for coolant leaking from the pump or a whining noise at the front of the engine.", "Torch", "hard", (5000, 20000, 4000, 9000)),
   ("gasket", "Head gasket leak", "engine", 0.10, "critical", False, "Combustion gases or coolant leak between the engine block and head.", "Look for white exhaust smoke, milky oil on the dipstick or constantly bubbling coolant.", "None", "hard", (8000, 30000, 25000, 60000))],
  links=[("cool", 300010, "often"), ("cool", 100549, "always"), ("cool", 300011, "often"), ("cool", 300012, "often"), ("cool", 103354, "sometimes"),
         ("thermo", 300010, "often"), ("thermo", 300012, "often"), ("thermo", 102851, "rarely"),
         ("fan", 100940, "always"), ("fan", 103354, "always"), ("fan", 102851, "always"), ("fan", 300010, "often"),
         ("pump", 300010, "often"), ("pump", 300011, "sometimes"), ("pump", 100549, "sometimes"), ("pump", 300012, "sometimes"),
         ("gasket", 300010, "often"), ("gasket", 300011, "often"), ("gasket", 100549, "sometimes"), ("gasket", 300012, "sometimes")],
  questions=[
   (300010, "When does the temperature rise?", "Temperature kab barhta hai?", 1,
    [("Mostly when stopped or in traffic", "Zyada tar ruke hue ya traffic mein", 103354), ("Also while driving at speed", "Raftaar par chalte hue bhi", 300010), ("Mainly with the AC on", "Zyada tar AC chalne par", 102851)]),
   (100940, "When the engine is hot, does the cooling fan stay off?", "Engine garam hone par kya cooling fan band rehta hai?", 0, None),
   (100549, "Is the coolant tank low, or do you see coolant under the car or smell something sweet?", "Kya coolant ka tank kam hai, ya gaari ke neeche coolant ya meethi boo hai?", 0, None),
   (300011, "Do you see steam or smoke coming from under the bonnet?", "Kya bonnet ke neeche se bhaap ya dhuan nikal raha hai?", 0, None),
   (300012, "Does the heater blow cold air while the engine is hot?", "Kya engine garam hone par bhi heater thandi hawa deta hai?", 0, None),
   (300010, "Does the temperature gauge climb above the middle mark?", "Kya temperature gauge beech ke nishan se upar jata hai?", 0, None),
   (103354, "Does the temperature mainly rise when the car is stopped or idling in traffic?", "Kya temperature zyada tar ruke hue ya traffic mein barhta hai?", 0, None)]),

 dict(category=9005,
  symptoms=[
   (300021, "shaking-when-braking", "Steering wheel or brake pedal shakes when braking", "Brake lagane par steering ya brake pedal hilta hai", False),
   (300022, "squealing-when-braking", "Squealing or screeching noise when braking", "Brake lagane par cheekhne ki awaaz aati hai", False),
   (300023, "grinding-when-braking", "Grinding noise when braking", "Brake lagane par ragadne ki awaaz aati hai", False),
   (300024, "brake-pedal-soft", "Brake pedal feels soft or sinks toward the floor", "Brake pedal naram lagta hai ya neeche tak chala jata hai", True),
   (300025, "pulls-to-one-side-braking", "Car pulls to one side when braking", "Brake lagane par gaari aik taraf kheenchti hai", False)],
  causes=[
   ("disc", "Warped brake discs", "brakes", 0.30, "medium", True, "Uneven discs make the pedal and steering shake under braking.", "Brake gently from about 80 km/h on a clear road: shaking that grows with speed points to the discs.", "None", "easy", (6000, 25000, 2000, 5000)),
   ("pads", "Worn brake pads", "brakes", 0.35, "medium", True, "Thin pads squeal, then grind against the disc.", "Look through the wheel spokes at the pad thickness. Under about 3 mm means replace.", "Torch", "easy", (3000, 12000, 1000, 3000)),
   ("caliper", "Seized brake caliper", "brakes", 0.10, "high", True, "A stuck caliper drags on one wheel and pulls the car sideways.", "After a drive, one wheel hub being much hotter than the others suggests a seized caliper.", "None", "medium", (5000, 20000, 2000, 5000)),
   ("fluid", "Brake fluid leak or air in the brake lines", "brakes", 0.10, "critical", False, "Lost pressure in the brake system makes the pedal soft.", "Check the brake fluid level and look for wet patches behind the wheels. Do not drive if the pedal sinks.", "Torch", "medium", (2000, 15000, 2000, 6000))],
  links=[("disc", 300021, "always"), ("disc", 300025, "rarely"), ("disc", 300022, "rarely"),
         ("pads", 300022, "always"), ("pads", 300023, "often"), ("pads", 300021, "sometimes"), ("pads", 300024, "rarely"),
         ("caliper", 300025, "always"), ("caliper", 300021, "sometimes"), ("caliper", 300022, "sometimes"), ("caliper", 300023, "sometimes"),
         ("fluid", 300024, "always"), ("fluid", 300025, "sometimes"), ("fluid", 300021, "rarely")],
  questions=[
   (300022, "What do you notice when you brake?", "Brake lagane par aap ko kya mehsoos hota hai?", 1,
    [("Shaking in the pedal or steering", "Pedal ya steering mein hilna", 300021), ("Squealing or screeching", "Cheekhne ki awaaz", 300022), ("Grinding", "Ragadne ki awaaz", 300023), ("The pedal feels soft or sinks", "Pedal naram lagta hai ya neeche jata hai", 300024)]),
   (300021, "Does the steering wheel or brake pedal shake when you brake from speed?", "Kya raftaar se brake lagane par steering ya pedal hilta hai?", 0, None),
   (300022, "Do you hear a squealing or screeching noise when you brake?", "Kya brake lagane par cheekhne ki awaaz aati hai?", 0, None),
   (300023, "Do you hear a metal grinding noise when you brake?", "Kya brake lagane par dhaat ke ragadne ki awaaz aati hai?", 0, None),
   (300025, "Does the car pull to one side when you brake?", "Kya brake lagane par gaari aik taraf kheenchti hai?", 0, None),
   (300024, "Does the brake pedal feel soft or sink toward the floor?", "Kya brake pedal naram lagta hai ya neeche tak chala jata hai?", 0, None)]),

 dict(category=9009,
  symptoms=[
   (300031, "ac-compressor-no-click", "No click from the engine bay when the AC is switched on", "AC on karne par engine bay se click ki awaaz nahi aati", False),
   (300032, "weak-airflow-vents", "Weak airflow from the vents even at full fan speed", "Poori fan speed par bhi vents se hawa kamzor aati hai", False),
   (300033, "ac-cold-only-while-driving", "AC is cold while driving but warm when stopped", "AC chalte hue thanda hai lekin ruke hue garam", False),
   (300034, "hissing-or-oily-ac-pipes", "Hissing sound or oily residue near the AC pipes", "AC ke pipes ke qareeb hissing ya tel jaisa nishan", False)],
  causes=[
   ("gas", "Low refrigerant or a leak in the AC system", "ac", 0.40, "low", True, "Not enough gas is left to cool the air.", "Look for oily patches on AC pipe joints. A gas refill that fades in weeks means there is a leak.", "Torch", "medium", (2000, 8000, 1000, 3000)),
   ("comp", "Compressor or compressor clutch failure", "ac", 0.15, "medium", True, "The compressor does not pump gas around the system.", "With the AC on, the centre of the compressor pulley should spin. If it does not, the clutch is not engaging.", "None", "hard", (15000, 50000, 4000, 9000)),
   ("cfan", "Condenser fan not working", "ac", 0.15, "low", True, "Without airflow over the condenser the AC fades at idle.", "At idle with the AC on, the front fan should run. If it is still, check its fuse and relay.", "None", "medium", (3000, 12000, 1500, 3500)),
   ("filt", "Blocked cabin filter or weak blower", "ac", 0.20, "low", True, "Airflow is restricted so cooling feels weak.", "Inspect the cabin filter behind the glovebox. A dirty filter is cheap to replace.", "Screwdriver", "easy", (500, 4000, 0, 1000)),
   ("fuse", "Blown AC fuse or relay", "electrical", 0.10, "low", True, "The compressor clutch gets no power.", "Check the AC fuse and relay in the fuse box using the manual.", "Spare fuse", "easy", (100, 1500, 0, 1000))],
  links=[("gas", 100036, "always"), ("gas", 300034, "often"), ("gas", 300033, "sometimes"), ("gas", 300031, "sometimes"),
         ("comp", 100036, "always"), ("comp", 300031, "often"), ("comp", 300034, "rarely"),
         ("cfan", 100036, "often"), ("cfan", 300033, "always"),
         ("filt", 300032, "always"), ("filt", 100036, "sometimes"),
         ("fuse", 300031, "always"), ("fuse", 100036, "often")],
  questions=[
   (100036, "How is the air from the vents?", "Vents se hawa kaisi aati hai?", 1,
    [("Warm, not cold at all", "Garam, bilkul thandi nahi", 100036), ("Cold only while driving, warm when stopped", "Chalte hue thandi, ruke hue garam", 300033), ("Cool but the airflow is weak", "Thandi lekin hawa kamzor", 300032)]),
   (300031, "With the engine running and the AC on, can you not hear a click as the compressor engages?", "Engine chalu aur AC on karne par kya compressor lagne ki click nahi aati?", 0, None),
   (300034, "Do you hear hissing or see oily residue near the AC pipes?", "Kya AC ke pipes ke qareeb hissing ya tel jaisa nishan hai?", 0, None),
   (300033, "Is the AC cold while driving but warm when you stop?", "Kya AC chalte hue thanda lekin ruke hue garam hota hai?", 0, None),
   (300032, "Is the airflow weak even with the fan at full speed?", "Kya poori fan speed par bhi hawa kamzor hai?", 0, None)]),

 dict(category=9010,
  symptoms=[
   (300041, "needs-jump-start", "Car needs a jump-start after sitting for a day or two", "Aik do din khari rehne ke baad gaari ko dhakka ya jump start chahiye", False),
   (300042, "battery-older-than-three-years", "Battery is more than three to four years old", "Battery teen se chaar saal se purani hai", False),
   (300043, "headlights-dim-battery-light", "Headlights dim at idle or the battery light comes on while driving", "Idle par headlights dheemi ya chalte hue battery light jal jati hai", False),
   (300044, "something-left-on", "Something stays on after the car is locked", "Gaari lock karne ke baad bhi koi cheez on rehti hai", False),
   (300045, "terminals-loose-or-corroded", "Battery terminals are loose or covered in crust", "Battery ke terminals dheelay ya zang se dhake hue hain", False)],
  causes=[
   ("oldb", "Old or worn-out battery", "electrical", 0.40, "low", True, "The battery can no longer hold a full charge.", "Have the battery load-tested at a shop (often free). Age over 3 to 4 years makes this likely.", "None", "easy", (12000, 30000, 0, 1000)),
   ("alt", "Faulty alternator", "electrical", 0.20, "medium", True, "The battery is not recharged while driving.", "With the engine running, a healthy alternator shows about 13.8 to 14.4 V across the battery.", "Multimeter", "medium", (10000, 40000, 2000, 6000)),
   ("drain", "Parasitic drain from a device left on", "electrical", 0.20, "low", True, "Something keeps drawing current after the car is off.", "Check boot, glovebox and interior lights, and unplug dashcams or chargers overnight.", "None", "medium", (0, 3000, 1500, 5000)),
   ("termb", "Loose or corroded battery terminals", "electrical", 0.10, "low", True, "Poor contact stops proper charging and starting.", "Check both terminals are tight and clean.", "Spanner, wire brush", "easy", (0, 500, 500, 1500))],
  links=[("oldb", 100120, "always"), ("oldb", 100125, "often"), ("oldb", 300041, "often"), ("oldb", 300042, "always"),
         ("alt", 100120, "often"), ("alt", 300043, "always"), ("alt", 300041, "sometimes"),
         ("drain", 100125, "always"), ("drain", 300044, "always"), ("drain", 300041, "often"), ("drain", 100120, "often"),
         ("termb", 300045, "always"), ("termb", 100120, "sometimes"), ("termb", 300041, "sometimes")],
  questions=[
   (100120, "How does the battery problem show up?", "Battery ka masla kaise samne aata hai?", 1,
    [("Dead after sitting overnight or a day", "Raat ya din bhar khari rehne ke baad dead", 100125), ("Dies or lights dim while driving", "Chalte hue band ya lights dheemi", 300043), ("Slow cranking, needs a jump-start", "Start dheemay hota hai, jump start chahiye", 300041)]),
   (300041, "Does the car need a jump-start after sitting for a day or two?", "Kya aik do din khari rehne ke baad gaari ko jump start chahiye?", 0, None),
   (300042, "Is the battery more than three to four years old?", "Kya battery teen se chaar saal se purani hai?", 0, None),
   (300043, "Do the headlights dim at idle, or does the battery light come on while driving?", "Kya idle par headlights dheemi hoti hain ya chalte hue battery light jalti hai?", 0, None),
   (300044, "Could something be left on after you lock the car (interior light, dashcam, stereo)?", "Kya gaari lock karne ke baad koi cheez on reh sakti hai (light, dashcam, stereo)?", 0, None),
   (300045, "Do the battery terminals look loose or covered in white or green crust?", "Kya battery ke terminals dheelay ya safaid/hare zang se dhake hain?", 0, None)]),
]

out, CAUSE = [], {}
def add(model, pk, fields): out.append({"model": model, "pk": pk, "fields": fields})
cause_pk, link_pk, q_pk, opt_pk, sc_pk, cost_pk = 300101, 301001, 300201, 302001, 304001, 303001

for p in PROBLEMS:
    for pk, key, en, ro, safety in p["symptoms"]:
        add("knowledge.symptom", pk, {**GOV, "key": key, "category": p["category"], "text_en": en,
            "text_roman": ro, "text_ur": "", "is_safety_critical": safety,
            "is_observable": True, "is_generic": False})
    for alias, name, system, prior, sev, safe, desc, steps, tools, diff, cost in p["causes"]:
        CAUSE[alias] = cause_pk
        add("knowledge.cause", cause_pk, {**GOV, "name": name, "system": system, "description": desc,
            "proof_hint": f"Ask the mechanic to show the test or measurement that confirms: {name.lower()}.",
            "prior": f"{prior:.3f}", "severity": sev, "safe_to_drive": safe, "car_models": []})
        add("knowledge.selfcheck", sc_pk, {**GOV, "cause": cause_pk, "steps": steps,
            "tools_needed": tools, "difficulty": diff})
        pmin, pmax, lmin, lmax = cost   # PLACEHOLDER prices: replace with verified quotes
        add("knowledge.repaircost", cost_pk, {**GOV, "status": "draft", "is_dummy": True, "cause": cause_pk,
            "city": "Lahore", "parts_min": pmin, "parts_max": pmax, "labour_min": lmin, "labour_max": lmax,
            "last_verified": "2026-10-30", "source": "PLACEHOLDER - replace with a verified quote"})
        cause_pk += 1; sc_pk += 1; cost_pk += 1
    for alias, symptom, strength in p["links"]:
        add("knowledge.causesymptomlink", link_pk, {"cause": CAUSE[alias], "symptom": symptom,
            "strength": strength, "weight": W[strength], "car_model": None})
        link_pk += 1
    for symptom, en, ro, triage, options in p["questions"]:
        add("knowledge.question", q_pk, {**GOV, "symptom": symptom, "text_en": en, "text_roman": ro,
            "text_ur": "", "type": "single_choice" if options else "yes_no", "media_url": "",
            "is_context": False, "is_triage": bool(triage), "triage_order": triage,
            "requires_symptom": None})
        rows = ([(l, r, "confirms", s) for l, r, s in options] if options else YN)
        rows = rows + [("Not sure", "Pata nahi", "unsure", None)]
        for label, roman, effect, implies in rows:
            add("knowledge.answeroption", opt_pk, {"question": q_pk, "label": label, "label_roman": roman,
                "label_ur": "", "is_unsure": effect == "unsure", "implies_symptom": implies,
                "effect": effect, "context_key": "", "context_value": ""})
            opt_pk += 1
        q_pk += 1

with open("./fixtures/core_problems.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print(len(out), "objects written")