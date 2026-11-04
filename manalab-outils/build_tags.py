"""Télécharge depuis Scryfall les listes utilisées pour le bracket :
Game Changers, tours supplémentaires, destruction massive de terrains, tuteurs (≤ 3 mana).
Usage : python3 build_tags.py   (écrit tags/bracket_tags.json à côté du script, lu par build_db.py)"""
import json, os, time, urllib.parse, urllib.request
def search(q):
    names, url = [], "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": q, "unique": "cards"})
    while url:
        req = urllib.request.Request(url, headers={"User-Agent": "ManaLab/1.0", "Accept": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        names += [c["name"] for c in d["data"]]
        url = d.get("next_page"); time.sleep(0.15)
    return names
Q = {"gc": "is:gamechanger", "xt": "otag:extra-turn", "mld": "otag:mass-land-denial",
     "tut": "otag:tutor -otag:tutor-land -otag:tutor-seek cmc<=3"}
out = {k: search(q) for k, q in Q.items()}
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "bracket_tags.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(out, open(p, "w"))
print({k: len(v) for k, v in out.items()})
