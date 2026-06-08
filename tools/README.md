# Forgejo Tools

Tools zur Analyse und Verarbeitung von Forgejo-Konfigurationsdateien.

Die Pipeline besteht aus drei Schritten:

1. `fetch` – holt die `.ini`-Konfiguration aus allen Git-Tags (>= 7.0.0) des Forgejo-Repos.
2. `clean` – entfernt die erläuternden Kommentare aus den INI-Dateien.
3. `diff` – vergleicht die versionierten INI-Dateien eines Ordners untereinander.

## Setup (uv)

```bash
uv sync
```

## Nutzung

```bash
uv run forgejo-tools fetch --repo https://codeberg.org/forgejo/forgejo.git --target custom/conf --out /tmp/forgejo
uv run forgejo-tools clean --in-dir /tmp/forgejo --out-dir /tmp/forgejo_clean
uv run forgejo-tools diff  --in-dir /tmp/forgejo_clean
```

## Tests

```bash
uv run pytest
```
