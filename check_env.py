import sys
from importlib.metadata import version

print("python         :", sys.version.split()[0])
for pkg in ("requests", "requests-cache", "pytest"):
    print(f"{pkg:15s}:", version(pkg))
print("venv active    :", sys.prefix != sys.base_prefix)
print("STEP 1 OK")