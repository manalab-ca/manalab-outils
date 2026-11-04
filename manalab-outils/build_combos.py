# Build combos.json from Commander Spellbook's public bulk export.
#   python3 build_combos.py variants.json.gz combos.json
# Download: https://json.commanderspellbook.com/variants.json.gz  (refreshed regularly by Commander Spellbook)
import gzip, json, sys, os

SRC, OUT = sys.argv[1], sys.argv[2]
opener = gzip.open if SRC.endswith(".gz") else open
with opener(SRC, "rt", encoding="utf-8") as f:
    data = json.load(f)

cards, card_idx = [], {}
feats, feat_idx = [], {}
tpls, tpl_idx = [], {}

def idx(lst, mp, key):
    if key not in mp:
        mp[key] = len(lst); lst.append(key)
    return mp[key]

rows = []
skipped = 0
for v in data.get("variants", []):
    if v.get("status") not in ("OK", "E", None):
        skipped += 1; continue
    uses = v.get("uses") or []
    if not uses:
        skipped += 1; continue
    ci, cmd = [], 0
    for u in uses:
        name = (u.get("card") or {}).get("name")
        if not name:
            continue
        for _ in range(max(1, int(u.get("quantity") or 1))):
            if u.get("mustBeCommander"):
                cmd |= 1 << len(ci)
            ci.append(idx(cards, card_idx, name))
    ti = [idx(tpls, tpl_idx, (r.get("template") or {}).get("name") or "?") for r in (v.get("requires") or [])]
    fi = [idx(feats, feat_idx, (p.get("feature") or {}).get("name") or "?") for p in (v.get("produces") or [])]
    leg = v.get("legalities") or {}
    rows.append([
        v.get("id"), ci, cmd, ti, fi,
        v.get("identity") or "C",
        v.get("bracketTag") or "",
        v.get("popularity") or 0,
        v.get("manaValueNeeded") or 0,
        1 if leg.get("commander", True) else 0,
    ])

rows.sort(key=lambda r: -r[7])
out = {
    "built": data.get("timestamp"),
    "source": "Commander Spellbook (commanderspellbook.com)",
    "cards": cards, "feat": feats, "tpl": tpls,
    "cols": ["id", "cards", "cmdMask", "tpl", "feat", "identity", "bracketTag", "popularity", "mvNeeded", "cmdLegal"],
    "v": rows,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("variants", len(rows), "skipped", skipped, "cards", len(cards), "features", len(feats), "templates", len(tpls), "size", os.path.getsize(OUT))
