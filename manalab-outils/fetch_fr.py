"""Noms (et textes) français des cartes depuis Scryfall -> fr.json : {nom anglais: [nom fr, set, numéro, type fr, texte fr]}"""
import json, time, urllib.parse, urllib.request
out = {}
url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": "lang:fr", "unique": "cards"})
n = 0
while url:
    for a in range(5):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ManaLab/1.0", "Accept": "application/json"}), timeout=60)); break
        except Exception:
            time.sleep(3 + a * 3)
    else: raise SystemExit("échec " + url)
    for c in d["data"]:
        faces = c.get("card_faces") or []
        pn = c.get("printed_name") or " // ".join(f.get("printed_name", "") for f in faces if f.get("printed_name")) or ""
        pt = c.get("printed_type_line") or " // ".join(f.get("printed_type_line", "") for f in faces if f.get("printed_type_line")) or ""
        tx = c.get("printed_text") or "\n— \n".join(f.get("printed_text", "") for f in faces if f.get("printed_text")) or ""
        iu = c.get("image_uris") or (faces[0].get("image_uris") if faces else None) or {}
        img = iu.get("normal", "").split("/front/")[-1].split("?")[0] if iu.get("normal") else ""
        if pn: out[c["name"]] = [pn, c["set"], c["collector_number"], pt, tx, img]
    n += 1
    url = d.get("next_page"); time.sleep(0.11)
names = {k: [v[0], v[5]] for k, v in out.items()}
texts = {k: [v[3], v[4]] for k, v in out.items()}
json.dump(names, open("frnames.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(texts, open("frtext.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(out), "cartes", n, "pages")
