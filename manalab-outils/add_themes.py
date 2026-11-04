"""Add the Scryfall theme tags to cards.json: each card gets g.tm = "mill,blink,…" (keys of tags/scryfall_themes.json).
   python3 add_themes.py cards.json"""
import json, os, sys
p = sys.argv[1]
db = json.load(open(p))
tags = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "scryfall_themes.json")))
by = {}
for k, names in tags.items():
    for n in names:
        for key in {n.lower(), n.split(" // ")[0].lower()}:
            by.setdefault(key, set()).add(k)
gi, hit = db["cols"].index("g") if isinstance(db["cols"], list) else db["cols"]["g"], 0
ni = db["cols"].index("n") if isinstance(db["cols"], list) else db["cols"]["n"]
for r in db["rows"]:
    n = r[ni]; nm = n[2:] if n.startswith("A-") else n
    ks = by.get(nm.lower()) or by.get(nm.split(" // ")[0].lower())
    g = r[gi] if isinstance(r[gi], dict) else {}
    if ks:
        g["tm"] = ",".join(sorted(ks)); hit += 1
    elif "tm" in g: del g["tm"]
    r[gi] = g
db["meta"]["themes"] = "Scryfall oracle tags"
json.dump(db, open(p, "w"), separators=(",", ":"), ensure_ascii=False)
print("cartes avec thème :", hit)
