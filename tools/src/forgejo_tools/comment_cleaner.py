import os
import re
from forgejo_tools.colors import bcolors


def remove_comments(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as infile, \
            open(output_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            stripped = line.strip()
            if not stripped or stripped.startswith(';;') or stripped.startswith('#'):
                continue
            # normalize: '; [' → ';['
            # nur am Zeilenanfang, damit z.B. URLs o.ä. nicht betroffen werden
            line = re.sub(r'^;\s+\[', ';[', line)
            outfile.write(line)


def clean_ini_directory(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.endswith(".ini"):
            in_path = os.path.join(input_dir, filename)
            out_path = os.path.join(output_dir, filename.replace(".ini", ".clean.ini"))
            remove_comments(in_path, out_path)
            print(bcolors.info(f"Cleaned: {filename}"))
