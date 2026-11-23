#!/usr/bin/env python3
"""Contrôles automatiques de Hangar FS 2024, lancés avant chaque compilation (GitHub Actions).

But : arrêter la compilation AVANT qu'une version cassée parte chez les utilisateurs.
  1. syntaxe JavaScript de chaque page (scripts intégrés aux pages .html et fichiers .js) ;
  2. pages FMS française et anglaise identiques (la langue est choisie à l'affichage) ;
  3. pages françaises et anglaises de même structure (mêmes blocs, dans le même ordre) ;
  4. pas de bloc en double (même id deux fois dans une page) ;
  5. pas de reste de fusion (<<<<<<< / >>>>>>>) dans les fichiers ;
  6. aucune trace d'un PC en particulier (chemin C:\\Users\\nom…) dans le code ;
  7. version.json lisible ; pour une publication, numéro de version cohérent partout.

Usage : python csharp/tools/check_pages.py   (variable REL = numéro publié, facultative)
Code de sortie 0 = tout va bien, 1 = au moins un problème (la liste est affichée).
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CS = os.path.join(ROOT, "csharp")
problems = []


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def node_check(code, where):
    fd, tmp = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            msg = "\n".join(l for l in r.stderr.splitlines() if l.strip() and tmp not in l)[:600]
            problems.append("Erreur JavaScript dans %s :\n%s" % (where, msg))
    finally:
        os.remove(tmp)


SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.S)
BLOCK_ID_RE = re.compile(r"<(script|style)\b[^>]*\bid=\"([^\"]+)\"")

pages = [os.path.join(CS, "web", f) for f in sorted(os.listdir(os.path.join(CS, "web"))) if f.endswith(".html")]
pages += [os.path.join(CS, "ui", "index.html"), os.path.join(CS, "tools", "fms_page_template.html")]
pages = [p for p in pages if os.path.exists(p)]

# 1. syntaxe
for p in pages:
    s = read(p)
    for i, m in enumerate(SCRIPT_RE.finditer(s)):
        attrs = m.group(1)
        if re.search(r"type=\"(?!text/javascript)[^\"]+\"", attrs):   # JSON, modèles… : pas du JavaScript
            continue
        line = s.count("\n", 0, m.start()) + 1
        node_check(m.group(2), "%s (script n°%d, ligne %d)" % (rel(p), i + 1, line))
for d in ("web",):
    for f in sorted(os.listdir(os.path.join(CS, d))):
        if f.endswith(".js") and f != "qrcode.js":
            p = os.path.join(CS, d, f)
            code = read(p)
            if code.lstrip().startswith("<"):    # morceau de page injecté par l'appli (<style>, <script>…)
                for i, m in enumerate(SCRIPT_RE.finditer(code)):
                    node_check(m.group(2), "%s (script n°%d)" % (rel(p), i + 1))
            else:
                node_check(code, rel(p))

# 2. FMS : les pages FR et EN sont le modèle tools/fms_page_template.html, seule la langue change
tpl = os.path.join(CS, "tools", "fms_page_template.html")
if os.path.exists(tpl):
    t = read(tpl)
    for lg in ("fr", "en"):
        p = os.path.join(CS, "web", "fms_%s.html" % lg)
        if os.path.exists(p) and read(p) != t.replace("__LANG__", lg):
            problems.append("web/fms_%s.html ne correspond plus au modèle tools/fms_page_template.html "
                            "(une modification n'a été faite que dans l'un des trois fichiers)." % lg)

# 3 et 4. structure FR / EN et blocs en double
for p in pages:
    s = read(p)
    ids = [m.group(2) for m in BLOCK_ID_RE.finditer(s)]
    seen = set()
    for x in ids:
        if x in seen:
            problems.append("%s : le bloc « %s » est présent deux fois." % (rel(p), x))
        seen.add(x)
for name in ("dispatch", "map", "tutorial"):
    a, b = os.path.join(CS, "web", name + "_fr.html"), os.path.join(CS, "web", name + "_en.html")
    if not (os.path.exists(a) and os.path.exists(b)):
        continue
    sa, sb = read(a), read(b)
    ia = [m.group(2) for m in BLOCK_ID_RE.finditer(sa)]
    ib = [m.group(2) for m in BLOCK_ID_RE.finditer(sb)]
    if ia != ib:
        only_fr = [x for x in ia if x not in ib]
        only_en = [x for x in ib if x not in ia]
        problems.append("web/%s : blocs différents entre français et anglais (seulement en FR : %s ; seulement en EN : %s)."
                        % (name, ", ".join(only_fr) or "—", ", ".join(only_en) or "—"))
    na, nb = len(SCRIPT_RE.findall(sa)), len(SCRIPT_RE.findall(sb))
    if na != nb:
        problems.append("web/%s : %d scripts en français, %d en anglais." % (name, na, nb))

# 5 et 6. restes de fusion, traces d'un PC
TEXT_EXT = (".cs", ".html", ".js", ".py", ".txt", ".md", ".json", ".csproj", ".yml", ".css")
PC_RE = re.compile(r"[A-Za-z]:\\{1,2}Users\\{1,2}(?!Public\b|Default\b|%|<|\{|\"|\\)[A-Za-z0-9._-]+", re.I)
for base, _dirs, files in os.walk(CS):
    if any(x in base for x in (os.sep + "bin", os.sep + "obj", os.sep + ".git")):
        continue
    for f in files:
        if not f.endswith(TEXT_EXT) or f == "check_pages.py":
            continue
        p = os.path.join(base, f)
        try:
            s = read(p)
        except UnicodeDecodeError:
            continue
        for m in re.finditer(r"^(<{7}|>{7})( |$)", s, re.M):
            problems.append("%s ligne %d : reste de fusion « %s »." % (rel(p), s.count("\n", 0, m.start()) + 1, m.group(1)))
            break
        m = PC_RE.search(s)
        if m:
            problems.append("%s ligne %d : chemin d'un PC en particulier (%s) — le code doit rester générique."
                            % (rel(p), s.count("\n", 0, m.start()) + 1, m.group(0)))

# 7. version
try:
    vj = json.loads(read(os.path.join(ROOT, "version.json")))
except Exception as e:  # noqa: BLE001
    problems.append("version.json illisible : %s" % e)
    vj = {}
REL = (os.environ.get("REL") or "").strip()
if REL:
    core = read(os.path.join(CS, "Core.cs"))
    m = re.search(r'public const string Version = "([^"]+)"', core)
    if not m or m.group(1) != REL:
        problems.append("Publication %s : Core.cs annonce la version %s." % (REL, m.group(1) if m else "?"))
    notes = read(os.path.join(CS, "docs", "release_notes.md"))
    first = next((l for l in notes.splitlines() if l.strip()), "")
    if not re.search(r"(?<![\d.])" + re.escape(REL) + r"(?![\d.])", first):
        problems.append("Publication %s : le titre de docs/release_notes.md ne mentionne pas cette version." % REL)

if problems:
    print("✗ %d problème(s) trouvé(s) :\n" % len(problems))
    for x in problems:
        print("- " + x + "\n")
    sys.exit(1)
print("✓ Contrôles OK : %d pages, syntaxe, langues, version." % len(pages))
