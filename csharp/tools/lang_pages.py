#!/usr/bin/env python3
"""Une seule page pour les deux langues : la page française est la source, la page anglaise en est fabriquée.

Pages concernées : web/dispatch_fr.html (Plan & suivi de vol), web/map_fr.html, web/tutorial_fr.html.
Pour chacune, tools/i18n/<page>_en.json liste les lignes à traduire (ligne française -> ligne anglaise) ;
tout le reste (le code) est recopié tel quel, donc le français et l'anglais ne peuvent plus diverger.

  python tools/lang_pages.py build     fabrique les pages anglaises à partir des pages françaises
  python tools/lang_pages.py check     vérifie que les pages anglaises sont à jour (utilisé par check_pages.py)
  python tools/lang_pages.py extract   reconstruit les tables de traduction à partir des pages FR et EN actuelles
                                       (après une modification faite dans les deux langues)

Règle : une modification de code se fait dans la page française, puis « build ».
Si une ligne traduite a changé en français, « build » s'arrête et dit laquelle : il faut alors refaire sa traduction.
"""
import difflib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")
I18N = os.path.join(HERE, "i18n")
PAGES = ("dispatch", "map", "tutorial")


def _read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def _write(p, s):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def table_path(page):
    return os.path.join(I18N, page + "_en.json")


def extract(page):
    fr = _read(os.path.join(WEB, page + "_fr.html")).split("\n")
    en = _read(os.path.join(WEB, page + "_en.html")).split("\n")
    lines = []
    for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, fr, en, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if op != "replace" or a1 - a0 != b1 - b0:
            raise SystemExit("%s : les pages FR et EN n'ont plus les mêmes lignes (lignes %d-%d) — "
                             "elles doivent rester alignées ligne à ligne." % (page, a0 + 1, a1))
        for i in range(a1 - a0):
            lines.append({"fr": fr[a0 + i], "en": en[b0 + i]})
    # une même ligne française peut apparaître plusieurs fois : on garde les traductions dans l'ordre
    merged, order = {}, []
    for x in lines:
        if x["fr"] not in merged:
            merged[x["fr"]] = []
            order.append(x["fr"])
        merged[x["fr"]].append(x["en"])
    out = []
    for k in order:
        v = merged[k]
        out.append({"fr": k, "en": v[0] if len(set(v)) == 1 else v})
    os.makedirs(I18N, exist_ok=True)
    _write(table_path(page), json.dumps({"page": page, "lines": out}, ensure_ascii=False, indent=1) + "\n")
    return len(lines)


def transfer(old_fr, new_fr, old_en):
    """Reporte sur la ligne anglaise une modification de code faite sur la ligne française.
    Possible seulement si les morceaux modifiés sont identiques en français et en anglais (du code, pas du texte)."""
    eq = [blk for blk in difflib.SequenceMatcher(None, old_fr, old_en, autojunk=False).get_matching_blocks() if blk.size]

    def pos(p, lo_edge):   # position dans la ligne anglaise, si p est dans une partie commune
        for i, j, n in eq:
            if i <= p <= i + n and (n or lo_edge):
                return j + (p - i)
        return None
    edits = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old_fr, new_fr, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        e1, e2 = pos(i1, True), pos(i2, True)
        if e1 is None or e2 is None or e2 < e1:
            return None
        # le morceau modifié doit être entièrement dans une même partie commune
        if not any(i <= i1 and i2 <= i + n for i, j, n in eq):
            return None
        edits.append((e1, e2, new_fr[j1:j2]))
    out = old_en
    for e1, e2, txt in sorted(edits, reverse=True):
        out = out[:e1] + txt + out[e2:]
    return out


def build_text(page, learn=None):
    fr = _read(os.path.join(WEB, page + "_fr.html")).split("\n")
    tab = json.loads(_read(table_path(page)))["lines"]
    want = {x["fr"]: x["en"] for x in tab}
    present = set(fr)
    orphans = [x for x in tab if x["fr"] not in present]
    new = {}
    if orphans:   # lignes traduites modifiées en français : reporter la modification si c'est du code
        for line in fr:
            if line in want or line in new or not line.strip():
                continue
            best, score = None, 0.0
            for o in orphans:
                sm = difflib.SequenceMatcher(None, o["fr"], line, autojunk=False)
                if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                    continue
                r = sm.ratio()
                if r > score:
                    best, score = o, r
            if best is None or score < 0.6 or isinstance(best["en"], list):
                continue
            t = transfer(best["fr"], line, best["en"])
            if t is not None:
                new[line] = t
                best["_done"] = True
        orphans = [o for o in orphans if not o.get("_done")]
    used, seen, out = set(), {}, []
    for line in fr:
        if line in want or line in new:
            t = want.get(line, new.get(line))
            if isinstance(t, list):
                k = seen.get(line, 0)
                seen[line] = k + 1
                t = t[min(k, len(t) - 1)]
            used.add(line)
            out.append(t)
        else:
            out.append(line)
    if learn is not None:   # nouvelle table : lignes encore utilisées + reports automatiques
        learn.extend([x for x in tab if x["fr"] in used and not x.get("_done")])
        learn.extend({"fr": k, "en": v} for k, v in new.items())
    return "\n".join(out), [o["fr"] for o in orphans]


def build(page, write=True):
    learn = []
    text, orphans = build_text(page, learn)
    if orphans:
        msg = "\n".join("   « %s »" % (o[:160] + ("…" if len(o) > 160 else "")) for o in orphans[:8])
        raise SystemExit("%s : %d ligne(s) traduite(s) introuvable(s) dans la page française "
                         "(modifiée en français ? refaire la traduction) :\n%s" % (page, len(orphans), msg))
    p = os.path.join(WEB, page + "_en.html")
    if write:
        _write(p, text)
        _write(table_path(page), json.dumps({"page": page, "lines": learn}, ensure_ascii=False, indent=1) + "\n")
    return text == _read(p) if os.path.exists(p) else False


def check():
    """Liste des problèmes (vide = tout va bien)."""
    problems = []
    for page in PAGES:
        if not os.path.exists(table_path(page)):
            problems.append("tools/i18n/%s_en.json manquant." % page)
            continue
        try:
            text, orphans = build_text(page)
        except SystemExit as e:
            problems.append(str(e))
            continue
        if orphans:
            problems.append("%s : %d ligne(s) traduite(s) n'existent plus dans la page française — refaire leur traduction "
                            "(python csharp/tools/lang_pages.py extract après correction des deux pages)." % (page, len(orphans)))
        elif text != _read(os.path.join(WEB, page + "_en.html")):
            problems.append("web/%s_en.html n'est plus fabriquée à partir de web/%s_fr.html "
                            "(lancer python csharp/tools/lang_pages.py build, ou extract si l'anglais a été modifié à la main)." % (page, page))
    return problems


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "extract":
        for pg in PAGES:
            print("%s : %d lignes traduites" % (pg, extract(pg)))
    elif cmd == "build":
        for pg in PAGES:
            build(pg)
            print("%s_en.html fabriquée" % pg)
    else:
        pr = check()
        print("\n".join(pr) if pr else "✓ pages anglaises à jour")
        sys.exit(1 if pr else 0)
