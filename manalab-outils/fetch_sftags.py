"""Download Scryfall oracle-tag card lists used to cross-check (and complete) the Forge-derived roles."""
import json, os, sys, time, urllib.parse, urllib.request
TAGS = {"ramp": ["ramp"], "draw": ["draw"], "rem": ["creature-removal"], "wipe": ["sweeper"], "ae": ["artifact-removal", "enchantment-removal"],
        "recur": ["recursion"], "tutor": ["tutor"], "ctr": ["counterspell"], "prot": ["protects-creature"], "sacout": ["sacrifice-outlet"],
        "deathtrig": ["death-trigger"], "fin": ["win-condition"], "burn": ["burn"]}
def search(q):
    names, url = [], "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": q, "unique": "cards"})
    while url:
        for attempt in range(4):
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ManaLab/1.0", "Accept": "application/json"}), timeout=60)); break
            except Exception as e:
                time.sleep(2 + attempt * 3)
        else: raise SystemExit("échec " + url)
        names += [c["name"] for c in d["data"]]
        url = d.get("next_page"); time.sleep(0.12)
    return names
out = {}
for k, tags in TAGS.items():
    s = set()
    for t in tags: s.update(search("otag:" + t))
    out[k] = sorted(s); print(k, len(s), flush=True)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "scryfall_roles.json")
json.dump(out, open(p, "w"))
