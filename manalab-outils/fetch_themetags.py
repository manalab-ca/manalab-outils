"""Download the Scryfall oracle-tag lists used to recognise deck themes (mill, blink, reanimator…).
Writes tags/scryfall_themes.json: {theme key: [card names]}. Run it at each new set, before add_themes.py."""
import json, os, time, urllib.parse, urllib.request
THEME_TAGS = {
    "mill": ["mill"], "selfmill": ["self-mill"], "blink": ["flicker"], "reani": ["reanimate", "cheat-into-play"],
    "sac": ["sacrifice-outlet"], "dies": ["death-trigger"], "life": ["lifegain-matters", "lifegain"], "drain": ["life-drain"],
    "xcombat": ["extra-combat"], "wheel": ["wheel"], "punish": ["punisher"], "discard": ["discard"], "loot": ["discard-outlet", "madness"],
    "theft": ["theft"], "lands": ["landfall"], "p1p1": ["counters-matter"], "artifact": ["artifact-matters"], "pillow": ["pillowfort"],
    "hug": ["group-hug"], "anthem": ["anthem"], "copy": ["copy", "clone"], "gycast": ["cast-from-graveyard", "flashback"],
    "stax": ["tax", "hatebear"], "spells": ["magecraft", "prowess-like"], "xturn": ["extra-turn"]
}
def search(q):
    names, url = [], "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": q, "unique": "cards"})
    while url:
        for attempt in range(5):
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ManaLab/1.0", "Accept": "application/json"}), timeout=60)); break
            except Exception:
                time.sleep(2 + attempt * 3)
        else:
            raise SystemExit("échec " + url)
        names += [c["name"] for c in d["data"]]
        url = d.get("next_page"); time.sleep(0.12)
    return names
out = {}
for k, tags in THEME_TAGS.items():
    s = set()
    for t in tags: s.update(search("otag:" + t + " legal:commander"))
    out[k] = sorted(s); print(k, len(s), flush=True)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "scryfall_themes.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(out, open(p, "w"))
