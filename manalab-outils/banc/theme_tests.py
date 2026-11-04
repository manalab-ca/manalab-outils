"""Archetype bench: theme detection on known precons, and the upgrade plan never cutting a deck's key cards.
   python3 theme_tests.py   (needs the local server on 8768)"""
import asyncio, json
from playwright.async_api import async_playwright
SP = './decks/'
precons = {x['name']: x for x in json.load(open('precons.json'))}
# precon → theme keys accepted as the main theme
EXPECT = {
  "Grave Danger [SCD] [2022]": ["typal_Zombie"], "Elven Empire [KHC] [2021]": ["typal_Elf"], "Blood Rites [LCC] [2023]": ["typal_Vampire"],
  "Draconic Domination [C17] [2017]": ["typal_Dragon"], "Arcane Wizardry [C17] [2017]": ["typal_Wizard"], "Buckle Up [NEC] [2022]": ["vehicles", "artifact"],
  "Exquisite Invention [C18] [2018]": ["artifact"], "Keen Engineering [FDC] [2026]": ["artifact"], "Creative Energy [M3C] [2024]": ["energy"],
  "Corrupting Influence [ONC] [2023]": ["poison", "typal_Phyrexian"], "Counter Blitz [FIC] [2025]": ["p1p1"], "Call for Backup [MOC] [2023]": ["p1p1"],
  "Death Toll [DSC] [2024]": ["selfmill", "reani", "mill"], "Land's Wrath [ZNC] [2020]": ["lands"], "Arm for Battle [CMR] [2020]": ["voltron"],
  "Aura of Courage [AFC] [2021]": ["voltron"], "Grand Larceny [OTC] [2024]": ["theft"], "Merciless Rage [C19] [2019]": ["loot"],
  "Adaptive Enchantment [C18] [2018]": ["ench", "voltron"], "Enhanced Evolution [C20] [2020]": ["mutate"], "Deadly Disguise [MKC] [2024]": ["facedown"],
  "Eternal Bargain [C13] [2013]": ["life"], "Ahoy Mateys [LCC] [2023]": ["typal_Pirate"], "Cabaretti Cacophony [NCC] [2022]": ["tokens"],
}
# deck file → cards the plan must never cut, for each goal
KEEP = {
  "mill.txt": ["Mesmeric Orb", "Geth, Lord of the Vault", "Mind Funeral", "Sheoldred, the Apocalypse", "Fraying Sanity", "Maddening Cacophony", "Bruvac the Grandiloquent", "Rhystic Study"],
  "ayara.txt": ["Blood Artist", "Zulaport Cutthroat", "Toxic Deluge", "Demonic Tutor", "Bolas's Citadel", "Gray Merchant of Asphodel"],
}
MAIN = {"mill.txt": ["mill"], "ayara.txt": ["sac", "dies", "drain"]}
JS = '''(D) => { var L = window.__labo, out = {};
  Object.keys(D).forEach(function (nm) { var x = D[nm], main = {};
    Object.keys(x.main).forEach(function (n) { var c = L.find(n); if (c) main[c.n] = (main[c.n] || 0) + x.main[n]; });
    var d = { id: "t-" + nm, name: nm, format: "commander", commanders: x.commanders.map(function (n) { var c = L.find(n); return c ? c.n : n; }), main: main, prints: {}, combos: [] };
    out[nm] = L.deckThemes(d).map(function (t) { return t.t.k; }); });
  return out; }'''
async def main():
    fails = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page()
        await pg.add_init_script('localStorage.setItem("labo.started","true")'); await pg.goto('http://localhost:8768/index.html#deck'); await pg.wait_for_function('document.getElementById("loading").hidden', timeout=90000)
        await pg.evaluate('__labo.loadCombos()'); await pg.wait_for_function('__labo.cbReady()', timeout=90000)
        got = await pg.evaluate(JS, {k: precons[k] for k in EXPECT})
        for k, exp in EXPECT.items():
            ok = bool(got[k]) and got[k][0] in exp
            if not ok: fails += 1
            print(("OK  " if ok else "FAIL"), k, "→", got[k][:3], "attendu", exp)
        for f, keep in KEEP.items():
            lst = open(SP + f).read()
            for goal in ("power", "both", "syn"):
                for cap in (3, 4):
                    r = await pg.evaluate('''([lst, goal, cap]) => { var L = window.__labo, P = L.parseList ? null : null; var d = L.importList(lst);
                        return L.upPrefetch(d, { goal: goal, budget: 0 }).p.then(function () {
                        var plan = L.upPlan(d, { goal: goal, cap: cap, budget: 0, n: 10 }); return { main: (L.deckThemes(d)[0] || {t:{}}).t.k, cuts: plan.swaps.filter(function (s) { return !s.forced; }).map(function (s) { return s.cut.n; }), forced: plan.swaps.filter(function (s) { return s.forced; }).map(function (s) { return s.cut.n; }) }; }); }''', [lst, goal, cap])
                    allowed = ["Sheoldred, the Apocalypse"] if goal == "syn" else []
                    bad = [c for c in r['cuts'] if c in keep and c not in allowed]
                    ok = not bad and r['main'] in MAIN[f]
                    if not ok: fails += 1
                    print(("OK  " if ok else "FAIL"), f, goal, "B%d" % cap, "thème", r['main'], "coupes", r['cuts'][:10], "imposées par le bracket", r['forced'], ("INTERDITES: " + str(bad)) if bad else "")
        await b.close()
    print("\n%d échec(s)" % fails)
asyncio.run(main())
