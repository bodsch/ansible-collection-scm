#!/usr/bin/python3

import argparse

from forgejo_tools import comment_cleaner, config_diff, repo_fetcher


def main():
    parser = argparse.ArgumentParser(description="Forgejo Tools CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Subparser: fetch
    fetch_parser = subparsers.add_parser("fetch", help="INI-Dateien aus Git-Tags holen")
    fetch_parser.add_argument("--repo", required=True, help="Git-Repository URL")
    fetch_parser.add_argument("--target", required=True, help="Pfad zur INI-Datei im Repo")
    fetch_parser.add_argument("--out", required=True, help="Zielordner für INI-Dateien")

    # Subparser: clean
    clean_parser = subparsers.add_parser("clean", help="Kommentare aus INI-Dateien entfernen")
    clean_parser.add_argument("--in-dir", required=True, help="Eingabeordner mit INI-Dateien")
    clean_parser.add_argument("--out-dir", required=True, help="Zielordner für bereinigte INIs")

    # Subparser: diff
    diff_parser = subparsers.add_parser("diff", help="Versionierte INI-Dateien eines Ordners vergleichen")
    diff_parser.add_argument("--in-dir", required=True, help="Eingabeordner mit INI-Dateien")

    args = parser.parse_args()

    if args.command == "fetch":
        repo_fetcher.fetch_ini_files(args.repo, args.target, args.out)
    elif args.command == "clean":
        comment_cleaner.clean_ini_directory(args.in_dir, args.out_dir)
    elif args.command == "diff":
        config_diff.ForgejoConfigDiff(args.in_dir).run()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
