# -*- coding: utf-8 -*-
"""FMS : fabrique web/fms_fr.html et web/fms_en.html à partir de tools/fms_page_template.html."""
import os
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "fms_page_template.html"), encoding="utf-8").read()
for lang in ("fr", "en"):
    out = os.path.join(here, "..", "web", "fms_%s.html" % lang)
    open(out, "w", encoding="utf-8", newline="\n").write(src.replace("__LANG__", lang))
    print("ok", out)
