

import re
import urllib3
import requests

class GitHub():
    """
    """
    def __init__(self, module):
        """
        """
        self.module = module
        self.module.log(msg=f"Github::__init__(module)")

        self.github_token = None  # z. B. 'ghp_...'
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }

        # Regex zum Erkennen von GitHub-Repository-URLs mit optionalem /releases
        self.github_url_re = re.compile(r"https://github\.com/([^/\s]+)/([^/\s]+)(?:/releases)?")

    def authentication(self, username: str = None, password: str = None, token: str = None):
        """
        """
        self.module.log(msg=f"Github::authentication({username}, {password}, {token})")
        if token:
            self.headers.update({
                "Authorization": f"token {token}"
            })

    def get_latest_release(self, repo_url: str):
        """
        """
        self.module.log(msg=f"Github::get_latest_release({repo_url})")

        user_repo = "/".join(repo_url.rstrip("/").split("/")[-2:])

        api_url = f"https://api.github.com/repos/{user_repo}/releases/latest"
        response = requests.get(api_url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            return {
                "repo": repo_url,
                "tag": data.get("tag_name"),
                "published": data.get("published_at")
            }
        elif response.status_code == 404:
            return {
                "repo": repo_url,
                "tag": None,
                "published": None
            }
        else:
            return {
                "repo": repo_url,
                "error": f"Fehlercode {response.status_code}"
            }

    def get_releases(self, repo_url: str, count: int = 10):
        """
        """
        self.module.log(msg=f"Github::get_releases({repo_url})")

        user_repo = "/".join(repo_url.rstrip("/").split("/")[-2:])

        api_url = f"https://api.github.com/repos/{user_repo}/releases"
        params = {
            "per_page": count
        }

        response = requests.get(api_url, headers=self.headers, params=params)

        if response.status_code == 200:
            releases = response.json()

            return [{
                "name": r.get("name"),
                "tag_name": r.get("tag_name"),
                "published_at": r.get("published_at"),
                "url": r.get("html_url")
            } for r in releases]

        elif response.status_code == 404:
            return {
                "repo": repo_url,
                "tag": None,
                "published": None
            }
        else:
            return {
                "repo": repo_url,
                "error": f"Fehlercode {response.status_code}"
            }

    def latest_information(self):
        """
        """
        output = None

        out_of_cache = cache_valid(self.module, self.cache_file_name, self.cache_minutes, True)

        if not out_of_cache:
            with open(self.cache_file_name, "r") as f:
                output = json.loads(f.read())

                return output

        if not output:
            self.module.log(msg=f" - read from url  {self.github_url}")

            status_code, output = self.__call_url()

            self.module.log(msg=f" - output  {output} {type(output)}")
            # convert the strings into a list
            output = output.split("\n")
            # and remove empty elements
            output[:] = [x for x in output if x]

            self.module.log(msg=f" - output  {output} {type(output)}")

            if status_code == 200:
                self.save_latest_information(output)

                return status_code, output
            else:
                return status_code, []


    def release_assets(self, owner, repo, tag):
        """
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/releases/tags/{tag}"

        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            assets = data.get("assets", [])
            return [{
                "name": asset["name"],
                "url": asset["browser_download_url"],
                "size": asset["size"]
            } for asset in assets]
        elif response.status_code == 404:
            return None  # Tag/Release nicht vorhanden
        else:
            raise Exception(f"Fehler beim Abrufen der Release-Assets: {response.status_code} - {response.text}")

    def has_checksum_file(self, owner, repo, tag):
        """
        """
        assets = self.release_assets(owner, repo, tag)
        if not assets:
            return False
        checksum_keywords = ["sha256", "sha512", "checksum", "sum"]
        for asset in assets:
            if any(kw in asset["name"].lower() for kw in checksum_keywords):
                return True
        return False

    def download_asset(self, url, filename):
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
        else:
            raise Exception(f"Fehler beim Herunterladen der Datei: {response.status_code}")


"""
gh = GitHub()
tag = "v1.2.3"
if gh.has_checksum_file("octocat", "Hello-World", tag):
    print(f"Für Release {tag} gibt es ein Checksum-File.")
else:
    print(f"Kein Checksum-File für Release {tag} gefunden.")
"""
