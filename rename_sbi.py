import os
import re

WIDGET = "frontend/templates/widget.html"
SBI_CLONE = "frontend/templates/sbi_clone.html"
NEXUS_CLONE = "frontend/templates/nexus.html"

# Fix widget.html
with open(WIDGET, "r", encoding="utf-8") as f:
    w_data = f.read()
w_data = w_data.replace("SBI Smart Assistant", "Nexus Smart Assistant")
with open(WIDGET, "w", encoding="utf-8") as f:
    f.write(w_data)

# Fix sbi_clone.html -> nexus.html
with open(SBI_CLONE, "r", encoding="utf-8") as f:
    n_data = f.read()

n_data = n_data.replace("--sbi-", "--nexus-")
n_data = n_data.replace("sbi-logo", "nexus-logo")
n_data = n_data.replace("sbi-gray", "nexus-gray")
n_data = n_data.replace("Online SBI", "Online Nexus")

# Replace EXACT word matches
n_data = re.sub(r'\bSBI\b', 'Nexus', n_data)
n_data = re.sub(r'\bSbi\b', 'Nexus', n_data)
n_data = re.sub(r'\bsbi\b', 'nexus', n_data)

with open(NEXUS_CLONE, "w", encoding="utf-8") as f:
    f.write(n_data)

os.remove(SBI_CLONE)
print("done")
