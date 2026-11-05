# ManaLab — outils

Les scripts qui fabriquent les données de [ManaLab](https://manalab.ca), le labo gratuit pour tes decks Magic: The Gathering (Commander, Standard, Arena).

*The scripts that build the data behind [ManaLab](https://manalab.ca), a free deck lab for Magic: The Gathering.*

## Ce qu'il y a ici

| Fichier | Rôle |
|---|---|
| `build_db.py` | Lit les scripts de règles du projet [Forge](https://github.com/Card-Forge/forge) et produit `cards.json` : chaque carte, ses rôles (rampe, pioche, retrait…), ses synergies et ses données de simulation. |
| `build_prints.py` | Produit `prints.json` : les éditions et versions de chaque carte. |
| `build_combos.py` | Produit `combos.json` à partir de l'export public de [Commander Spellbook](https://commanderspellbook.com). |
| `build_tags.py`, `fetch_sftags.py` | Récupèrent sur [Scryfall](https://scryfall.com) les Game Changers et des étiquettes de rôles. |
| `fetch_themetags.py`, `add_themes.py` | Récupèrent les étiquettes de thèmes de Scryfall (meule, blink, réanimation…) et les ajoutent à `cards.json`. |
| `fetch_ranks.py` | Récupère sur Scryfall le classement EDHREC de chaque carte (sert à la « qualité des cartes »). |
| `banc/calibrate.py` | Calibre l'indice de puissance : mesure combien de decks de référence tombent dans leur fourchette, et recalcule les poids (`--fit --apply index.html`). Accepte les avis des joueurs exportés de Supabase (`--reports reports.csv`). |
| `.github/workflows/banc.yml` | Lance le banc d'essai chaque lundi sur manalab.ca ; GitHub t'écrit si un test échoue. |
| `banc/theme_tests.py` | Banc d'essai par archétype : thème détecté sur des précons connus, et cartes que le plan d'amélioration ne doit jamais couper. |
| `fetch_fr.py` | Récupère les noms et textes français des cartes (Scryfall). |
| `to_js.py` | Convertit un `.json` en `.data.js` pour ouvrir le site sans serveur. |
| `compare_roles.py` | Compare les rôles détectés avec les étiquettes Scryfall. |
| `banc/` | Banc d'essai : précons officiels et listes cEDH pour calibrer l'indice de puissance. |
| `schema.sql` | Le schéma de la base Supabase (comptes optionnels, decks, liens de partage). |

## Utilisation

```bash
git clone --depth 1 https://github.com/Card-Forge/forge.git
python3 build_tags.py
python3 fetch_themetags.py
python3 fetch_ranks.py
python3 build_db.py forge/forge-gui/res cards.json
python3 add_themes.py cards.json
python3 build_prints.py forge/forge-gui/res prints.json cards.json
curl -O https://json.commanderspellbook.com/variants.json.gz
python3 build_combos.py variants.json.gz combos.json
python3 fetch_fr.py
```

Python 3.10+ ; aucune dépendance externe.

## Licence et sources

- Ces outils sont sous **licence GPL v3** (voir `LICENSE`), comme Forge, dont ils lisent les scripts de règles.
- Données de cartes, images et prix : [Scryfall](https://scryfall.com). Combos : [Commander Spellbook](https://commanderspellbook.com).
- ManaLab est un contenu de fan non officiel, permis par la Politique sur le contenu de fans. Non approuvé ni cautionné par Wizards. Certains éléments utilisés sont la propriété de Wizards of the Coast. ©Wizards of the Coast LLC.

Contact : bonjour@manalab.ca

## Recalibrer l'indice de puissance (une fois par mois)

1. Dans Supabase › Table Editor › `reports`, exporte la table en CSV (bouton **Export**) : ce sont les avis des joueurs (« Selon toi, combien ? »).
2. Lance un serveur local dans le dossier du site (`python3 -m http.server 8768`), puis :
   ```
   python3 banc/calibrate.py --fit --reports reports.csv              # montre le gain
   python3 banc/calibrate.py --fit --reports reports.csv --apply index.html
   ```
   Les nouveaux poids ne sont écrits que s'ils font au moins aussi bien que les anciens sur les decks de référence.
3. Relance `banc/theme_tests.py`, puis remets le site en ligne.
