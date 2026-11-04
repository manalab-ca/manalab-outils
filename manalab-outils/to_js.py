# Wrap a JSON data file as a .data.js file so index.html can also be opened by double-click.
#   python3 to_js.py cards.json cards.data.js
import sys, os
src, out = sys.argv[1], sys.argv[2]
name = os.path.basename(out).split(".")[0]
with open(src, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as o:
    o.write('window.LABO_DATA=window.LABO_DATA||{};window.LABO_DATA["%s"]=' % name)
    o.write(f.read())
    o.write(";\n")
print("ok", out)
