import os
import requests
import json
import time

class GitHubClient:
    """
    An enhanced client for interacting with the GitHub API.
    """
    def __init__(self, token=None, repo=None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo = repo or os.getenv("GITHUB_REPO", "kjs0113/nudge-test")
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        } if self.token else {}
        self._bot_login = None

    @property
    def bot_login(self):
        if self._bot_login is None and self.token:
            try:
                response = self._request("GET", "https://api.github.com/user")
                self._bot_login = response.json().get("login")
            except Exception as e:
                print(f"Failed to fetch bot login: {e}")
                self._bot_login = "trace-ledger-bot" # Fallback
        return self._bot_login

    def _request(self, method, url, data=None, retries=3):
        for i in range(retries):
            try:
                response = requests.request(method, url, headers=self.headers, data=data)
                if response.status_code == 403 and "rate limit" in response.text.lower():
                    wait_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60)) - time.time()
                    print(f"Rate limit hit. Waiting {wait_time}s...")
                    time.sleep(max(wait_time, 10))
                    continue
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if i == retries - 1: raise e
                time.sleep(2 ** i)

    def get_pull_request(self, pr_number):
        url = f"{self.base_url}/pulls/{pr_number}"
        return self._request("GET", url).json()

    def get_pr_files(self, pr_number):
        url = f"{self.base_url}/pulls/{pr_number}/files"
        return self._request("GET", url).json()

    def post_comment(self, pr_number, body):
        url = f"{self.base_url}/issues/{pr_number}/comments"
        data = json.dumps({"body": body})
        return self._request("POST", url, data=data).json()

    def get_comments(self, pr_number):
        url = f"{self.base_url}/issues/{pr_number}/comments"
        return self._request("GET", url).json()

if __name__ == "__main__":
    client = GitHubClient()
    print(f"GitHub Client initialized for repo: {client.repo}")
    if client.token:
        print(f"Authenticated as: {client.bot_login}")
