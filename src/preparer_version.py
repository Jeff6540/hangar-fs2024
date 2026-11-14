# Lit le numéro de version dans Hangar_FS2024.pyw et le recopie dans version_info.txt (infos du .exe).
import re
src = open("Hangar_FS2024.pyw", encoding="utf-8").read()
ver = re.search(r'^VERSION = "([\d.]+)"', src, re.M).group(1)
n = ([int(x) for x in ver.split(".")] + [0, 0, 0, 0])[:4]
info = open("version_info.txt", encoding="utf-8").read()
info = re.sub(r"(filevers|prodvers)=\([\d, ]+\)", lambda m: "%s=(%d, %d, %d, %d)" % (m.group(1), *n), info)
info = re.sub(r"'(FileVersion|ProductVersion)', '[\d.]+'", lambda m: "'%s', '%s'" % (m.group(1), ".".join(map(str, n))), info)
open("version_info.txt", "w", encoding="utf-8").write(info)
print(ver)
