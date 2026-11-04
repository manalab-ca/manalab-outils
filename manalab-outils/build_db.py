# Build a compact card database from Forge card scripts + editions + formats.
import os, re, json, sys, glob, datetime

RES = sys.argv[1]
OUT = sys.argv[2]
TODAY = __import__("datetime").date.today().isoformat()

# ---------- editions ----------
set_info = {}          # code -> (date, type, name)
card_sets = {}         # name -> list of (date, code, rarity)
for f in glob.glob(os.path.join(RES, "editions", "*.txt")):
    txt = open(f, encoding="utf-8", errors="replace").read()
    meta = {}
    sec = None
    cards = []
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            sec = m.group(1).lower()
            continue
        if sec == "metadata":
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip()] = v.strip()
            continue
        if sec is None or "token" in sec or sec in ("other",):
            continue
        if "=" in line and not re.match(r"^\S+\s+[CURMSLT]\s", line):
            continue
        line = re.sub(r"\s+@.*$", "", line)
        line = re.sub(r"\s+\$.*$", "", line)
        m = re.match(r"^(\S+)\s+([CURMSLT])\s+(.+)$", line)
        if m:
            cards.append((m.group(3).strip(), m.group(2)))
    code = meta.get("Code")
    if not code:
        continue
    date = meta.get("Date", "1993-01-01")
    typ = meta.get("Type", "")
    set_info[code] = (date, typ, meta.get("Name", code))
    for name, rar in cards:
        card_sets.setdefault(name, []).append((date, code, rar))

# ---------- formats ----------
def read_format(path):
    d = {}
    for line in open(path, encoding="utf-8"):
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    sets = set(s.strip() for s in d.get("Sets", "").split(",") if s.strip())
    banned = set(s.strip() for s in d.get("Banned", "").split(";") if s.strip())
    restricted = set(s.strip() for s in d.get("Restricted", "").split(";") if s.strip())
    return sets, banned
F = {}
F["standard"] = read_format(os.path.join(RES, "formats/Sanctioned/Standard.txt"))
F["historic"] = read_format(os.path.join(RES, "formats/Sanctioned/Historic.txt"))
F["pioneer"] = read_format(os.path.join(RES, "formats/Sanctioned/Pioneer.txt"))
F["modern"] = read_format(os.path.join(RES, "formats/Sanctioned/Modern.txt"))
alch = sorted(glob.glob(os.path.join(RES, "formats/Archived/Alchemy/*.txt")))[-1]
F["alchemy"] = read_format(alch)
cmd_banned = read_format(os.path.join(RES, "formats/Casual/Commander.txt"))[1]
FMT_BITS = {"standard": 1, "commander": 2, "historic": 4, "alchemy": 8, "pioneer": 16, "modern": 32}

# ---------- card scripts ----------
COLOR_WORD = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
BASIC = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}

def parse_face(block):
    d = {"A": [], "T": [], "S": [], "K": [], "SVar": {}, "R": []}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k in ("A", "T", "S", "K", "R"):
            d[k].append(v)
        elif k == "SVar":
            if ":" in v:
                a, b = v.split(":", 1)
                d["SVar"][a] = b
        else:
            d[k] = v
    return d

def cost_parts(mc):
    """Forge cost '2 R R' -> (generic, pips list, symbol string, cmc)"""
    if not mc or mc.strip() == "no cost":
        return 0, [], "", 0
    generic = 0
    pips = []
    sym = ""
    cmc = 0
    for tok in mc.split():
        if tok.isdigit():
            generic += int(tok); cmc += int(tok); sym += "{%s}" % tok
        elif tok == "X":
            sym += "{X}"
        elif tok == "C":
            pips.append("C"); cmc += 1; sym += "{C}"
        elif tok == "S":
            generic += 1; cmc += 1; sym += "{S}"
        elif "/" in tok or (len(tok) == 2 and (tok[0] in "WUBRG2" and tok[1] in "WUBRGP")):
            a, b = tok.split("/") if "/" in tok else (tok[0], tok[1])
            sym += "{%s/%s}" % (a, b)
            if b == "P":
                pips.append(a + "L"); cmc += 1          # phyrexian: colour or life
            elif a == "2":
                pips.append(b + "2"); cmc += 2          # twobrid
            else:
                pips.append(a + b); cmc += 1            # hybrid
        elif tok in "WUBRG":
            pips.append(tok); cmc += 1; sym += "{%s}" % tok
        else:
            sym += "{%s}" % tok
    return generic, pips, sym, cmc

def num(v, default=1):
    try:
        return int(v)
    except Exception:
        return default

def kv(line):
    out = {}
    for part in line.split("|"):
        part = part.strip()
        if "$" in part:
            k, v = part.split("$", 1)
            out[k.strip()] = v.strip()
    return out

def chain(face, name, seen):
    out = []
    while name and name not in seen and name in face["SVar"]:
        seen.add(name)
        e = kv(face["SVar"][name])
        out.append(e)
        for k in ("SubAbility", "Execute"):
            if k in e and e[k] in face["SVar"] and e[k] not in seen:
                out += chain(face, e[k], seen)
        name = None
    return out

def effects(face):
    """(source, params): source 'A' activated/spell, 'E' one-shot ETB trigger, 'R' repeating trigger."""
    effs = []
    seen = set()
    for a in face["A"]:
        e = kv(a)
        effs.append(("A", e))
        if "SubAbility" in e:
            for x in chain(face, e["SubAbility"], seen):
                x = dict(x)
                if "AB" in e: x["AB"] = x.pop("DB", x.get("AB"))
                effs.append(("A", x))
    for t in face["T"]:
        e = kv(t)
        vcard = e.get("ValidCard", "")
        etb = e.get("Mode") in ("ChangesZone", "ChangesZoneAll") and "Self" in vcard and "," not in vcard and e.get("Destination", "") == "Battlefield"
        cast = e.get("Mode") == "SpellCast" and "Self" in e.get("ValidCard", "")
        src = "E" if (etb or cast) else "R"
        for x in chain(face, e.get("Execute", ""), seen):
            effs.append((src, x))
    for k in face["K"]:
        if k.startswith("Chapter"):
            for nm in k.split(":")[-1].split(","):
                for x in chain(face, nm, seen):
                    effs.append(("E", x))
        if k.startswith("Etbcounter") or k.startswith("ETBReplacement"):
            pass
    for nm, s in face["SVar"].items():
        if nm not in seen and ("DB$" in s or "AB$" in s or "SP$" in s):
            effs.append(("A", kv(s)))
    return effs

def api(e):
    for k in ("SP", "AB", "DB"):
        if k in e:
            return k, e[k]
    return None, None

def clean_oracle(o):
    o = (o or "").replace("\\n", "\n")
    o = re.sub(r"\s*\([^()]*\)", "", o)  # reminder text
    return o.strip()

# ---- synergy: what a card produces for others (pz) and what it waits for (cz) ----
# D death · M -1/-1 counter · P +1/+1 counter · T token · E creature enters · F sacrifice fodder · L life gain · N land enters · S sacrifice
def syn_tags(face, types, oracle_raw):
    pz, cz = set(), set()
    ol = oracle_raw.lower()
    tl = types.split()
    for t in face["T"]:
        e = kv(t)
        mode, vc = e.get("Mode", ""), e.get("ValidCard", "")
        self_only = vc.replace("Card.Self", "").replace("Creature.Self", "").strip(",") == "" and "Self" in vc
        if mode in ("ChangesZone", "ChangesZoneAll") and "Battlefield" in e.get("Origin", "") and e.get("Destination", "") == "Graveyard":
            if self_only:
                if "Creature" in tl: pz.add("F")
            elif any(x in vc for x in ("Creature", "EquippedBy", "AttachedBy", "Permanent", "Card.Other", "Card.YouCtrl")) or vc == "":
                cz.add("D")
                if "counters_GE1_M1M1" in vc: cz.add("M")
        elif mode in ("ChangesZone", "ChangesZoneAll") and e.get("Destination", "") == "Battlefield" and not self_only:
            if "Land" in vc: cz.add("N")
            elif "Creature" in vc: cz.add("E")
        elif mode in ("CounterAdded", "CounterAddedOnce", "CounterAddedAll"):
            ct = e.get("CounterType", "")
            if ct == "M1M1": cz.add("M")
            elif ct == "P1P1": cz.add("P")
        elif mode == "LifeGained": cz.add("L")
        elif mode in ("Sacrificed", "SacrificedOnce"): cz.add("S"); cz.add("D")
        elif mode in ("TokenCreated", "TokenCreatedOnce"): cz.add("T")
    for src, e in effects(face):
        kind, ap = api(e)
        cost = e.get("Cost", "")
        if re.search(r"Sac<\d+/(Creature|Permanent|Card)", cost) or ("Sac<" in cost and "Creature" in cost and "CARDNAME" not in cost):
            cz.add("F"); pz.add("D"); pz.add("S")
        if "AddCounter<" in cost and "M1M1" in cost: pz.add("M")
        if "SubCounter<" in cost and "M1M1" in cost and "Creature" in cost: cz.add("M")
        if not ap: continue
        ct = e.get("CounterType", "")
        if ap in ("PutCounter", "PutCounterAll", "MoveCounter"):
            if ct == "M1M1": pz.add("M")
            elif ct == "P1P1": pz.add("P")
        elif ap == "Proliferate": pz.update("MP")
        elif ap == "Token":
            ts = e.get("TokenScript", "")
            if re.search(r"(^|,)[wubrgcl]+_\d+_\d+", ts): pz.update("TEF")
            elif ts: pz.add("T")
        elif ap in ("Destroy", "DestroyAll", "DamageAll") or (ap == "Sacrifice" and "Creature" in e.get("SacValid", e.get("ValidTgts", "Creature"))):
            if ap == "Sacrifice" and e.get("Defined", "You") in ("You", "") and "Opp" not in e.get("Defined", ""): cz.add("F"); pz.add("S")
            pz.add("D")
        elif ap == "SacrificeAll": pz.add("D")
        elif ap == "GainLife": pz.add("L")
        elif ap == "ChangeZone" and "Graveyard" in e.get("Origin", "") and e.get("Destination") == "Battlefield": pz.update("EF")
        elif ap == "ChangeZone" and "Library" in e.get("Origin", "") and e.get("Destination") == "Battlefield" and "Land" in e.get("ChangeType", ""): pz.add("N")
        elif ap == "Pump" and "-" in e.get("NumDef", "") and "Creature" in e.get("ValidTgts", ""): pz.add("D")
    for k in face["K"]:
        k0 = k.split(":")[0].strip()
        if k0 in ("Persist", "Undying"):
            pz.update("FE" + ("M" if k0 == "Persist" else "P")); cz.add("P" if k0 == "Persist" else "M")
        if k0 == "etbCounter" and "M1M1" in k: pz.add("M")
        if k0 == "etbCounter" and "P1P1" in k: pz.add("P")
        if k0 == "Support": pz.add("P")
        if k0 in ("Wither", "Infect"): pz.add("M")
    for st in face["S"]:
        e = kv(st)
        if (e.get("Mode") == "Continuous" and any(x in e.get("AddKeyword", "") for x in ("Wither", "Infect"))) or e.get("Mode") == "WitherDamage": pz.add("M")
    if re.search(r"\bblight (\d|x)", ol): pz.add("M")
    if "Land" in tl: pz.add("N")
    return "".join(sorted(pz)), "".join(sorted(cz))

# ---- hate: what a card shuts down (hz) ----
# D deaths/dies triggers · G graveyard · M -1/-1 counters · E creatures entering · F sacrifice · A creature abilities · Q artifact abilities
def hate_tags(face):
    hz = set()
    for r in face["R"]:
        e = kv(r)
        if e.get("Event") == "Moved" and e.get("Destination") == "Graveyard" and e.get("ReplaceWith") == "Exile" and "Self" not in e.get("ValidCard", "") and e.get("ActiveZones", "") == "Battlefield":
            hz.update("DG")
        if e.get("Event") == "Moved" and "Graveyard" in e.get("Origin", "") and e.get("Prevent") == "True": hz.add("G")
        if e.get("Event") == "AddCounter" and "HalfCounters" in e.get("ReplaceWith", "") : hz.add("M")
    for st in face["S"]:
        e = kv(st)
        m = e.get("Mode", "")
        vcp = e.get("ValidCard", "") + e.get("Affected", "")
        if m == "CantPutCounter" and ("Self" in vcp or "Enchanted" in vcp or "Equipped" in vcp): pass
        elif m == "CantPutCounter" and "ValidCard" in e and e.get("CounterType", "") in ("", "M1M1"): hz.add("M")
        elif m == "DisableTriggers":
            if e.get("Destination") == "Battlefield": hz.add("E")
            if e.get("Destination") == "Graveyard": hz.add("D")
        elif m in ("CantSacrifice", "CantPayLife") and e.get("ForCost") == "True": hz.add("F")
        elif m == "CantBeActivated" and e.get("AffectedZone", "Battlefield") == "Battlefield" and not re.search(r"Self|Enchanted|Equipped|Attached|Targeted|IsRemembered|Chosen", e.get("ValidCard", "")):
            vc = e.get("ValidCard", "")
            if vc.startswith("Creature") or vc == "Permanent": hz.add("A")
            if vc.startswith("Artifact") or vc == "Permanent": hz.add("Q")
        elif m == "CantBeCast" and "Graveyard" in e.get("Origin", ""): hz.add("G")
    for src, e in effects(face):
        kind, ap = api(e)
        if ap == "ChangeZoneAll" and "Graveyard" in e.get("Origin", "") and e.get("Destination") == "Exile": hz.add("G")
    return "".join(sorted(hz))

def sim_profile(face, types, oracle_raw):
    g = {}
    ol = oracle_raw.lower()
    is_land = "Land" in types.split()
    is_creature = "Creature" in types.split()
    effs = effects(face)
    # ---- mana production ----
    prod = set()
    amount = 0
    for a in face["A"]:
        e = kv(a)
        if e.get("AB") == "ManaReflected" and "T" in e.get("Cost", "").split() and "Sac<" not in e.get("Cost", ""):
            prod.update("WUBRG"); amount = max(amount, 1)
        if e.get("AB") == "Mana":
            cost = e.get("Cost", "")
            if "T" in cost.split() or cost.startswith("T"):
                p = e.get("Produced", "C")
                amt = num(e.get("Amount", "1"), 1)
                if "Sac<" in cost:
                    continue
                for tok in p.replace(",", " ").split():
                    if tok in ("Any", "Chosen", "ColorIdentity"):
                        prod.update("WUBRG")
                    elif tok == "Combo":
                        prod.update("WUBRG")
                    elif tok in ("W", "U", "B", "R", "G", "C"):
                        prod.add(tok)
                amount = max(amount, amt)
    for t, c in BASIC.items():
        if t in types.split():
            prod.add(c); amount = max(amount, 1)
    if is_land:
        tap = 0
        if re.search(r"enters( the battlefield)? tapped\.", ol) or "ETBTapped" in "".join(face["R"]) or any("ETBTapped" in k for k in face["K"]) or "CARDNAME enters tapped." in "".join(face["K"]):
            tap = 1
        if "enters tapped unless" in ol or ("unless you control" in ol and "tapped" in ol):
            tap = 2
        if "you may pay 2 life" in ol:
            tap = 0
        fetch = None
        m = re.search(r"search your library for an? ([a-z ,]+?) card", ol)
        if m and "sacrifice" in ol:
            words = m.group(1)
            fc = set()
            for t, c in BASIC.items():
                if t.lower() in words:
                    fc.add(c)
            if "basic land" in words or not fc:
                fc = set("WUBRG")
            prod.update(fc)
            fetch = 1
            if "put it onto the battlefield tapped" in ol:
                tap = 1
        if not prod and "add one mana of any color" in ol:
            prod.update("WUBRG")
        g["land"] = {"p": "".join(sorted(prod)) or "C", "tap": tap}
        if fetch:
            g["land"]["fetch"] = 1
    elif prod and amount:
        g["mana"] = {"p": "".join(sorted(prod)), "n": amount, "cr": 1 if is_creature else 0}

    # ---- spells / abilities ----
    for src, e in effs:
        kind, ap = api(e)
        if not ap:
            continue
        cost = e.get("Cost", "")
        repeat = (kind == "AB" and "Sac<1/CARDNAME" not in cost) or src == "R"
        if "Draw<" in cost:
            if repeat: g["engine"] = max(g.get("engine", 0), 1)
            else: g["draw"] = max(g.get("draw", 0), num(cost.split("Draw<")[1].split("/")[0], 1))
        if ap == "Mana" and ("Instant" in types.split() or "Sorcery" in types.split()):
            g["ritual"] = 1
        if ap == "ChangeZone":
            orig = e.get("Origin", ""); dest = e.get("Destination", "")
            ctype = e.get("ChangeType", "")
            landish = "Land" in ctype or any(b in ctype for b in ("Plains", "Island", "Swamp", "Mountain", "Forest", "Basic"))
            if ("Library" in orig or orig == "Hand") and dest == "Battlefield" and landish:
                g["ramp"] = max(g.get("ramp", 0), num(e.get("ChangeNum", "1"), 1))
            elif "Library" in orig and dest == "Hand" and landish and not is_land:
                g["fix"] = 1
            elif "Library" in orig and dest == "Battlefield" and ctype and not landish and e.get("Defined", "") == "":
                g["tutor"] = 1
            elif "Library" in orig and (dest == "Hand" or (dest == "Library" and e.get("LibraryPosition") == "0")) and ctype and not landish:
                g["tutor"] = 1
            elif "Library" in orig and dest in ("Hand", "Library") and e.get("ChangeType", "") in ("Card", "") and "Hidden" in e.get("Origin", "") + e.get("Hidden", ""):
                g["tutor"] = 1
            elif "Battlefield" in orig and dest in ("Exile", "Hand", "Library", "Graveyard") and "ValidTgts" in e:
                vt = e["ValidTgts"]
                if any(x in vt for x in ("Creature", "Permanent", "Card")) and "YouCtrl" not in vt:
                    g["rem"] = 1
                if any(x in vt for x in ("Artifact", "Enchantment", "Permanent", "nonLand")) and "YouCtrl" not in vt and dest != "Hand" or (dest == "Hand" and ("Artifact" in vt or "Enchantment" in vt) and "YouCtrl" not in vt):
                    g["ae"] = 1
            elif "Graveyard" in orig and dest in ("Hand", "Battlefield", "Library") and e.get("Defined", "") not in ("Self", "TriggeredCard", "TriggeredNewCardLKICopy") and ("ValidTgts" in e or ctype or "ChangeType" in e or e.get("Defined") == "Enchanted") and "Opp" not in e.get("ValidTgts", "") and not (dest == "Library" and e.get("LibraryPosition") not in ("0",)):
                g["recur"] = 1
        elif ap == "ChangeZoneAll":
            ct_ = e.get("ChangeType", "") + e.get("ValidCards", "")
            if "Battlefield" in e.get("Origin", "") and "Creature" in ct_:
                g["wipe"] = 1
            if "Battlefield" in e.get("Origin", "") and ("Artifact" in ct_ or "Enchantment" in ct_) and "YouCtrl" not in ct_:
                g["ae"] = 1
            if "Graveyard" in e.get("Origin", "") and e.get("Destination", "") in ("Hand", "Battlefield") and "Opp" not in ct_:
                g["recur"] = 1
        elif ap in ("Destroy", "Sacrifice") and "ValidTgts" in e:
            vt = e["ValidTgts"]
            if any(x in vt for x in ("Creature", "Permanent", "Planeswalker")) and "YouCtrl" not in vt:
                g["rem"] = 1
            if any(x in vt for x in ("Artifact", "Enchantment", "Permanent", "nonLand")) and "YouCtrl" not in vt and not vt.startswith("Land"):
                g["ae"] = 1
        elif ap == "Sacrifice" and "Defined" in e and "Opponent" in e.get("Defined", "") and "Creature" in e.get("SacValid", ""):
            g["rem"] = 1
        elif ap in ("DestroyAll", "DamageAll") or (ap == "PumpAll" and "-" in e.get("NumDef", "")):
            vc = e.get("ValidCards", "")
            if ap == "DestroyAll" and ("Artifact" in vc or "Enchantment" in vc) and "YouCtrl" not in vc:
                g["ae"] = 1
            if "Creature" in vc or ap == "DamageAll" or "Permanent" in vc:
                if "YouCtrl" not in vc and "OppCtrl" not in vc:
                    g["wipe"] = 1
                elif "OppCtrl" in vc:
                    g["wipe1"] = 1
        elif ap == "DealDamage":
            vt = e.get("ValidTgts", "") or e.get("Defined", "")
            nd = num(e.get("NumDmg", "0"), 0)
            if any(x in vt for x in ("Creature", "Any", "Permanent")) and nd >= 2:
                g["rem"] = 1
                if "Any" in vt or "Player" in vt:
                    g["burn"] = max(g.get("burn", 0), nd)
            elif ("Player" in vt or "Opponent" in vt) and nd:
                g["burn"] = max(g.get("burn", 0), nd)
        elif ap == "LoseLife" and ("Opponent" in e.get("Defined", "") or "Player" in e.get("Defined", "") or "Opponent" in e.get("ValidTgts", "") or "Player" in e.get("ValidTgts", "")):
            la = e.get("LifeAmount", "1")
            if repeat or src == "T" or not la.isdigit() or num(la, 0) >= 5:
                g["drain"] = 1
        elif ap in ("WinsGame",) or (ap == "LosesGame" and "Opponent" in e.get("Defined", "")):
            g["win"] = 1
        elif ap == "AddPhase" and "Combat" in e.get("ExtraPhase", "") + e.get("FollowedBy", "") + e.get("ExtraPhase", ""):
            g["xcombat"] = 1
        elif ap == "PumpAll" and "YouCtrl" in e.get("ValidCards", "") and (num(e.get("NumAtt", "0").lstrip("+"), 0) >= 2 or not e.get("NumAtt", "0").lstrip("+").isdigit() and e.get("NumAtt")):
            g["overrun"] = 1
        elif ap in ("CopyPermanent", "Clone", "CopySpellAbility"):
            g["copy"] = 1
        elif ap == "TwoPiles" or ap == "PeekAndReveal":
            g["draw"] = max(g.get("draw", 0), 2 if ap == "TwoPiles" else g.get("draw", 0) or 1)
        elif ap == "Mill" and e.get("Defined", "You") in ("You", ""):
            g["mill"] = 1
        elif ap == "AnimateAll" and "YouCtrl" in e.get("ValidCards", ""):
            g["overrun"] = 1
        elif ap == "Play":
            g["free"] = 1
        elif ap == "ChangeTargets":
            g["prot"] = 1
        elif ap == "Draw":
            n = num(e.get("NumCards", "1"), 1)
            if repeat:
                g["engine"] = max(g.get("engine", 0), 1)
            else:
                g["draw"] = max(g.get("draw", 0), n)
        elif ap == "Dig" and "Graveyard" in e.get("DestinationZone2", "") + e.get("DestinationZone", ""):
            g["mill"] = 1
            if e.get("DestinationZone", "Hand") in ("Hand", ""): g["draw"] = max(g.get("draw", 0), num(e.get("ChangeNum", "1"), 1))
        elif ap == "Dig" and e.get("DestinationZone", "") == "Exile" and "MayPlay" in " ".join(face["SVar"].values()):
            g["draw"] = max(g.get("draw", 0), num(e.get("DigNum", "1"), 1))
        elif ap == "Dig" and e.get("DestinationZone", "Hand") in ("Hand", ""):
            n = num(e.get("ChangeNum", "1"), 1)
            if "Land" not in e.get("ChangeValid", ""):
                g["draw"] = max(g.get("draw", 0), n)
        elif ap == "Counter":
            g["ctr"] = 1
        elif ap == "Token":
            ts = e.get("TokenScript", "")
            amt = num(e.get("TokenAmount", "1"), 1)
            pw = 0
            for t in ts.split(","):
                m = re.match(r"^[wubrgcl]+_(\d+)_(\d+)_", t)
                if m:
                    pw += int(m.group(1))
                if "treasure" in t and not m:
                    if repeat:
                        g["treng"] = 1
                    else:
                        g["treas"] = g.get("treas", 0) + amt
            if pw:
                g["tok"] = max(g.get("tok", 0), pw * amt)
                if repeat:
                    g["tokr"] = 1
        elif ap == "Pump" and "ValidTgts" in e and "Creature" in e.get("ValidTgts","") and num(e.get("NumAtt", "0").lstrip("+"), 0) > 0 and kind == "SP":
            g["pump"] = num(e.get("NumAtt", "0").lstrip("+"), 0)
            if "KW" in e and any(x in e["KW"] for x in ("Hexproof", "Indestructible")):
                g["prot"] = 1
        elif ap == "Pump" and "KW" in e:
            kw = e["KW"]
            if any(x in kw for x in ("Hexproof", "Indestructible", "Protection", "Shroud")):
                g["prot"] = 1
        elif ap == "PumpAll" and any(x in e.get("KW", "") for x in ("Hexproof", "Indestructible", "Shroud")) and "YouCtrl" in e.get("ValidCards", ""):
            g["prot"] = 1
        elif ap == "Protection" or ap == "PhaseOut":
            g["prot"] = 1
        elif ap == "GainLife":
            g["life"] = max(g.get("life", 0), num(e.get("LifeAmount", "0"), 0))
        elif ap == "PutCounter" and e.get("CounterType") == "M1M1" and "Creature" in e.get("ValidTgts", "") and "YouCtrl" not in e.get("ValidTgts", ""):
            g["rem"] = 1
        elif ap == "PutCounterAll" and e.get("CounterType") == "M1M1" and "Creature" in e.get("ValidCards", "") and "YouCtrl" not in e.get("ValidCards", ""):
            if "OppCtrl" in e.get("ValidCards", ""):
                g["wipe1"] = 1
            else:
                g["wipe"] = 1
    # static anthems
    for s in face["S"]:
        e = kv(s)
        md_ = e.get("Mode", "")
        if md_ == "CantAttackUnless": g["tax"] = 1
        if md_ == "ReduceCost" and e.get("Activator", "You") == "You": g["cheap"] = 1
        if md_ == "Continuous" and e.get("AffectedDefined") in ("Equipped", "Enchanted") and (e.get("AddPower") or e.get("AddKeyword")) and "Curse" not in types: g["equip"] = 1
        if md_ == "Continuous" and "YouCtrl" in e.get("Affected", "") and num(e.get("AddPower", "0").lstrip("+"), 0) > 0: g["anth"] = max(g.get("anth", 0), num(e.get("AddPower", "0").lstrip("+"), 0))
        if e.get("Mode") == "Continuous" and "YouCtrl" in e.get("Affected", "") and "Creature" in e.get("Affected", "") and "Other" not in e.get("Affected", "").split(".")[0] :
            ap_ = num(e.get("AddPower", "0").lstrip("+"), 0)
            if ap_ > 0:
                g["anth"] = ap_
        elif e.get("Mode") == "Continuous" and "YouCtrl" in e.get("Affected", "") and "Creature" in e.get("Affected", ""):
            ap_ = num(e.get("AddPower", "0").lstrip("+"), 0)
            if ap_ > 0:
                g["anth"] = ap_
        if e.get("Mode") == "Continuous" and any(k in e.get("AddKeyword", "") for k in ("Shroud", "Hexproof", "Indestructible")) and \
           (e.get("AffectedDefined") in ("Equipped", "Enchanted") or "YouCtrl" in e.get("Affected", "") or "Commander" in e.get("Affected", "")) and "Opp" not in e.get("Affected", ""):
            g["prot"] = 1
        if e.get("Mode") in ("CantBlockBy",) and e.get("ValidAttacker", "") in ("Creature.Self", "Card.Self"):
            g["evade"] = 1
        if e.get("Mode") == "CantAttack" or e.get("Mode") == "CantBlock":
            pass
    # graveyard recursion / drain fallbacks from text
    _cg = re.search(r"(cast|play) ([^.]*?) from your graveyard", ol)
    if "IsReanimatorCard" in face.get("SVar", {}) or (_cg and not re.search(r"cardname|this card|this creature|~", _cg.group(2))):
        g["recur"] = 1
    if re.search(r"return [^.]*cards? from (your|a) graveyard to (the battlefield|your hand)", ol) and not re.search(r"return (this card|~|" + re.escape(face.get("Name", "@").lower()) + r") from", ol):
        g["recur"] = 1
    m_ = re.search(r"(whenever[^.]*)?each opponent loses (x|\d+) life", ol)
    if m_ and (m_.group(1) or m_.group(2) == "x" or "repeat" in ol or int(m_.group(2) if m_.group(2).isdigit() else 0) >= 5):
        g["drain"] = 1
    # Pacifism-style auras
    if "Aura" in types and "Enchant creature" in oracle_raw and ("can't attack or block" in ol or "can't attack" in ol and "can't block" in ol):
        g["rem"] = 1
    for r_ in face["R"]:
        er = kv(r_)
        if er.get("Event") in ("AddCounter", "CreateToken") and re.search(r"More|Double|Twice", er.get("ReplaceWith", "")): g["dbl"] = 1
    if any("Prevent all combat damage" in k for k in face["K"]): g["fog"] = 1
    # keywords
    kws = []
    for k in face["K"]:
        k0 = k.split(":")[0].strip()
        if k0 in ("Flying", "Haste", "Trample", "Lifelink", "Vigilance", "Double Strike", "First Strike", "Menace", "Hexproof", "Indestructible", "Deathtouch", "Reach", "Flash", "Shroud", "Ward"):
            kws.append({"Flying": "F", "Haste": "H", "Trample": "T", "Lifelink": "L", "Vigilance": "V", "Double Strike": "D", "First Strike": "1", "Menace": "M", "Hexproof": "X", "Indestructible": "I", "Deathtouch": "K", "Reach": "R", "Flash": "f", "Shroud": "X", "Ward": "W"}[k0])
        if k0 == "Mobilize":
            g["tok"] = max(g.get("tok", 0), num(k.split(":")[1] if ":" in k else "1", 1))
            g["tokr"] = 1
    if "can't be blocked" in ol and "this creature" not in ol[:0]:
        if re.search(r"(this creature|~|" + ")can't be blocked", ol):
            g["evade"] = 1
    if kws:
        g["kw"] = "".join(sorted(set(kws)))
    return g

_bt = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "bracket_tags.json")))
def _names(lst):
    out = set()
    for n in lst:
        out.add(n)
        if " // " in n: out.add(n.split(" // ")[0])
    return out
_sfp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags", "scryfall_roles.json")
SFR = {k: _names(v) for k, v in json.load(open(_sfp)).items()} if os.path.exists(_sfp) else {}
BTAGS = {"gc": _names(_bt.get("gc", [])), "xt": _names(_bt.get("xt", [])), "mld": _names(_bt.get("mld", [])), "tut": _names(_bt.get("tut", []))}
records = {}
skipped = 0
files = []
for d in os.listdir(os.path.join(RES, "cardsfolder")):
    p = os.path.join(RES, "cardsfolder", d)
    if os.path.isdir(p):
        files += glob.glob(os.path.join(p, "*.txt"))

BAD_TYPES = {"Conspiracy", "Scheme", "Plane", "Phenomenon", "Vanguard", "Dungeon", "Attraction", "Contraption", "Emblem"}

for f in files:
    txt = open(f, encoding="utf-8", errors="replace").read()
    parts = re.split(r"\n\s*ALTERNATE\s*\n", txt)
    front = parse_face(parts[0])
    back = parse_face(parts[1]) if len(parts) > 1 else None
    name = front.get("Name", "").strip()
    if not name:
        continue
    types = front.get("Types", "").strip()
    if set(types.split()) & BAD_TYPES:
        skipped += 1; continue
    alt = front.get("AlternateMode", "").strip()
    display = name
    gen, pips, sym, cmc = cost_parts(front.get("ManaCost", ""))
    oracle_f = front.get("Oracle", "")
    oracle = clean_oracle(oracle_f)
    btypes = ""
    if back:
        bname = back.get("Name", "").strip()
        btypes = back.get("Types", "").strip()
        bo = clean_oracle(back.get("Oracle", ""))
        if alt == "Split":
            display = name + " // " + bname
            g2, p2, s2, c2 = cost_parts(back.get("ManaCost", ""))
            sym = sym + " // " + s2
            cmc = cmc + c2
            types = types if types == btypes else types + " // " + btypes
        else:
            if alt in ("Modal", "DoubleFaced", "Adventure", "Omen", "Prepare", "Flip"):
                display = name + " // " + bname if alt in ("Modal", "DoubleFaced", "Adventure", "Omen", "Prepare") else name
        oracle = oracle + "\n— " + bname + " (" + btypes + ") —\n" + bo
    # colours
    cols = set()
    for p_ in pips:
        for ch in p_:
            if ch in "WUBRG":
                cols.add(ch)
    if "Colors" in front:
        cols = set(COLOR_WORD.get(c.strip(), "") for c in front["Colors"].split(",")) - {""}
    ident = set(cols)
    full_or = (front.get("Oracle", "") + " " + (back.get("Oracle", "") if back else ""))
    for m in re.finditer(r"\{([^}]+)\}", full_or):
        for ch in m.group(1).split("/"):
            if ch in "WUBRG":
                ident.add(ch)
    if back:
        _, bp, _, _ = cost_parts(back.get("ManaCost", ""))
        for p_ in bp:
            for ch in p_:
                if ch in "WUBRG":
                    ident.add(ch)
        if "Colors" in back:
            ident |= set(COLOR_WORD.get(c.strip(), "") for c in back["Colors"].split(",")) - {""}
    for t, c in BASIC.items():
        if t in types.split():
            ident.add(c)
    # sim
    g = sim_profile(front, types, oracle_f)
    if back and alt == "Modal" and "Land" in btypes.split() and "Land" not in types.split():
        gb = sim_profile(back, btypes, back.get("Oracle", ""))
        if "land" in gb:
            g["mdfc"] = gb["land"]
    if alt == "Split" and back:
        gb = sim_profile(back, btypes, back.get("Oracle", ""))
        for k, v in gb.items():
            g.setdefault(k, v)
    # printings
    prints = card_sets.get(name, []) or card_sets.get(display, [])
    if not prints and back:
        prints = card_sets.get(name + " // " + back.get("Name", ""), [])
    released = [p_ for p_ in prints if p_[0] <= TODAY]
    upcoming = not released
    codes = set(p_[1] for p_ in released)
    lg = 0
    for fk in ("standard", "historic", "alchemy", "pioneer", "modern"):
        sets_, ban = F[fk]
        if codes & sets_ and name not in ban and display not in ban:
            lg |= FMT_BITS[fk]
    paper = [p_ for p_ in released if set_info.get(p_[1], ("", "", ""))[1] not in ("Online", "Funny")]
    if paper and name not in cmd_banned and display not in cmd_banned and not name.startswith("A-"):
        lg |= FMT_BITS["commander"]
    # rarity of latest print
    rar = ""
    latest = ""
    if released:
        lp = sorted(released)[-1]
        rar = lp[2]; latest = lp[1]
    elif prints:
        lp = sorted(prints)[-1]
        rar = lp[2]; latest = lp[1]
    tl = types.split()
    cmdr = 1 if (("Legendary" in tl and "Creature" in tl) or "can be your commander" in oracle_f) else 0
    rec = {
        "n": display, "m": sym, "v": cmc, "t": types,
        "o": oracle, "c": "".join(c for c in "WUBRG" if c in cols),
        "i": "".join(c for c in "WUBRG" if c in ident),
        "lg": lg, "pr": len(set(p_[1] for p_ in prints)), "s": latest, "r": rar,
    }
    if "PT" in front:
        pt = front["PT"].split("/")
        rec["pt"] = front["PT"]
        g["pw"] = num(pt[0], 0); g["th"] = num(pt[1] if len(pt) > 1 else "0", 0)
        if "*" in front["PT"]:
            st = " ".join(front["S"]) + " " + " ".join(front["SVar"].values())
            if "Creature.YouCtrl" in st:
                g["ptx"] = 1
            else:
                g["pw"] = max(g["pw"], 2); g["th"] = max(g["th"], 2)
    if "Loyalty" in front:
        rec["ly"] = front["Loyalty"]
    if pips:
        g["pips"] = pips
    g["gen"] = gen
    if "X" in front.get("ManaCost", "").split():
        g["x"] = 1
    if cmdr:
        g["cmdr"] = 1
    pz_, cz_ = syn_tags(front, types, oracle_f)
    if back and alt in ("Modal", "Split", "Adventure", "Omen", "Prepare"):
        pb, cb = syn_tags(back, btypes, back.get("Oracle", ""))
        pz_ = "".join(sorted(set(pz_) | set(pb))); cz_ = "".join(sorted(set(cz_) | set(cb)))
    if pz_ and "Land" not in types.split(): g["pz"] = pz_
    if cz_: g["cz"] = cz_
    hz_ = hate_tags(front)
    if hz_: g["hz"] = hz_
    tl_ = types.split()
    abs_ = [kv(x) for x in front["A"] if x.startswith("AB$") or "AB$" in x[:6]]
    if "Creature" in tl_ and any(e.get("AB") not in ("Mana", None) for e in abs_): g["ab"] = 1
    if "Artifact" in tl_ and abs_ and "Creature" not in tl_: g["abq"] = 1
    kwz = g.get("kw", "")
    if g.get("drain") or g.get("win") or g.get("xcombat") or g.get("overrun") or g.get("anth", 0) >= 2 or g.get("burn", 0) >= 5 \
       or (g.get("pw", 0) >= 7 and ("F" in kwz or "T" in kwz or "D" in kwz or g.get("evade"))) or g.get("pw", 0) >= 10:
        g["fin"] = 1
    # second opinion: Scryfall's hand-curated tags fill the roles the script rules missed
    if SFR and "Land" not in types.split():
        inS = lambda k: k in SFR and (name in SFR[k] or display in SFR[k])
        lo = oracle.lower(); add = ""
        if inS("ramp") and not (g.get("mana") or g.get("ramp") or g.get("treng") or g.get("ritual")): add += "r"
        if inS("rem") and not g.get("rem") and not g.get("wipe"): add += "k"
        if inS("wipe") and not (g.get("wipe") or g.get("wipe1")): add += "w"
        if inS("ae") and not g.get("ae"): add += "a"
        if inS("recur") and not g.get("recur") and re.search(r"(target|another|creature|permanent|cards?|instant|sorcery|artifact|enchantment) [^.]*from (your|a|their) graveyard", lo): add += "c"
        if inS("tutor") and not (g.get("tutor") or g.get("ramp") or g.get("fix")) and not re.search(r"basic land|land card", lo): add += "t"
        if inS("ctr") and not g.get("ctr"): add += "x"
        if inS("prot") and not g.get("prot"): add += "p"
        if add: g["sf"] = add
        if inS("sacout") and "F" not in g.get("cz", ""):
            g["cz"] = "".join(sorted(set(g.get("cz", "")) | {"F"})); g["pz"] = "".join(sorted(set(g.get("pz", "")) | {"D", "S"}))
        if inS("deathtrig") and "D" not in g.get("cz", ""):
            if re.search(r"(another creature|a creature|creatures? you control|nontoken creature|whenever a) [^.]*dies", lo): g["cz"] = "".join(sorted(set(g.get("cz", "")) | {"D"}))
            elif "Creature" in types.split(): g["pz"] = "".join(sorted(set(g.get("pz", "")) | {"F"}))
    for fk, tagset in BTAGS.items():
        if name in tagset or display in tagset:
            g[fk] = 1
    if upcoming:
        rec["up"] = 1
    rec["g"] = g
    key = display.lower()
    # keep the version with more printings if duplicate
    if key in records and records[key]["pr"] >= rec["pr"]:
        continue
    records[key] = rec

cards = sorted(records.values(), key=lambda r: r["n"])
meta = {"built": TODAY, "count": len(cards),
        "standardSets": sorted(F["standard"][0]),
        "source": "Forge card scripts (Card-Forge/forge), " + TODAY}
# compact: array of arrays
cols = ["n", "m", "v", "t", "o", "c", "i", "lg", "pr", "s", "r", "pt", "ly", "up", "g"]
rows = [[r.get(k, "" if k not in ("v", "lg", "pr") else 0) for k in cols] for r in cards]
json.dump({"meta": meta, "cols": cols, "rows": rows}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("cards", len(cards), "skipped", skipped, "size", os.path.getsize(OUT))
