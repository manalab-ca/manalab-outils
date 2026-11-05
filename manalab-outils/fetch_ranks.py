"""Download the EDHREC rank of every Commander-legal card from Scryfall (field edhrec_rank).
Writes tags/edhrec_ranks.json: {card name: rank}. Run it at each new set, before add_themes.py."""
import json, os, time, urllib.parse, urllib.request
url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": "legal:commander", "order": "edhrec", "unique": "cards"})
out, page = {}, 0
while url:
    for attempt in range(5):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ManaLab/1.0", "Accept": "application/json"}), timeout=60)); break
        except Exception:
            time.sleep(2 + attempt * 3)
    else:
        raise SystemExit("échec " + url)
    for c in d["data"]:
        if c.get("edhrec_rank"): out[c["name"]] = c["edhrec_rank"]
    page += 1
    if page % 20 == 0: print(page, len(out), flush=True)
    url = d.get("next_page"); time.sleep(0.11)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "edhrec_ranks.json")
json.dump(out, open(p, "w"))
print("cartes classées :", len(out))
