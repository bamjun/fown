import configparser
import os
import time
import webbrowser
from pathlib import Path

import click
import requests

# Constants
CLIENT_ID = "Ov23liZ6IrbJN0ISFh8h"
DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_BASE_URL = "https://api.github.com"
HEADERS = {"Accept": "application/json"}
SCOPE = "repo"

# Configuration file path
CONFIG_DIR = Path.home() / ".fown"
CONFIG_FILE = CONFIG_DIR / "config.ini"


def ensure_config_dir_exists():
    """Ensures the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_token(token):
    """Saves the GitHub token to the config file."""
    ensure_config_dir_exists()
    config = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)
    if "github" not in config:
        config["github"] = {}
    config["github"]["token"] = token
    with open(CONFIG_FILE, "w") as configfile:
        config.write(configfile)
    click.echo("Successfully logged in and saved token.")


def load_token():
    """Loads the GitHub token from the config file."""
    if not CONFIG_FILE.exists():
        return None
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config.get("github", "token", fallback=None)


def remove_token():
    """Removes the GitHub token from the config file."""
    if not CONFIG_FILE.exists():
        return
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    if "github" in config and "token" in config["github"]:
        del config["github"]["token"]
        with open(CONFIG_FILE, "w") as configfile:
            config.write(configfile)
        click.echo("Successfully logged out.")
    else:
        click.echo("You were not logged in.")


def get_login_status():
    """Checks if the user is logged in and the token is valid."""
    token = load_token()
    if not token:
        return None, "Not logged in. Please run 'fown login'."

    headers = {"Authorization": f"token {token}"}
    try:
        response = requests.get(f"{API_BASE_URL}/user", headers=headers)
        response.raise_for_status()
        user_data = response.json()
        return token, f"Logged in as {user_data['login']}."
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 401:
            return None, "Your token is invalid or has expired. Please log in again."
        return None, f"Failed to verify token: {e}"


@click.group(invoke_without_command=True)
@click.pass_context
def login(ctx):
    """
    Authenticate with GitHub.

    If no subcommand is specified, shows login status.
    """
    if ctx.invoked_subcommand is None:
        _, message = get_login_status()
        click.echo(message)


@login.command(name="start")
def start_login():
    """Start the GitHub device login flow."""
    token = load_token()
    if token:
        _, message = get_login_status()
        click.echo(f"You are already logged in. {message}")
        if click.confirm("Do you want to log in again?"):
            pass
        else:
            return

    try:
        response = requests.post(
            DEVICE_CODE_URL,
            headers=HEADERS,
            data={"client_id": CLIENT_ID, "scope": SCOPE},
        )
        response.raise_for_status()
        resp_data = response.json()
    except requests.exceptions.RequestException as e:
        click.echo(f"Error requesting device code: {e}", err=True)
        return

    user_code = resp_data["user_code"]
    device_code = resp_data["device_code"]
    verification_uri = resp_data["verification_uri"]
    expires_in = resp_data["expires_in"]
    interval = resp_data.get("interval", 5)

    click.echo(f"Your one-time code is: {click.style(user_code, fg='yellow', bold=True)}")
    if click.confirm("Press Enter to open a browser to the verification page...", default=True):
        webbrowser.open(verification_uri)
        click.echo(f"If the browser does not open, please visit: {verification_uri}")

    total_wait = 0
    with click.progressbar(length=expires_in, label="Waiting for authorization...") as bar:
        while total_wait < expires_in:
            time.sleep(interval)
            total_wait += interval
            bar.update(interval)

            try:
                poll_resp = requests.post(
                    TOKEN_URL,
                    headers=HEADERS,
                    data={
                        "client_id": CLIENT_ID,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                )
                poll_resp.raise_for_status()
                token_data = poll_resp.json()
            except requests.exceptions.RequestException:
                # Don't fail on polling errors, just continue
                continue

            if "access_token" in token_data:
                save_token(token_data["access_token"])
                return
            elif token_data.get("error") == "slow_down":
                interval += 5  # Increase interval if GitHub asks us to slow down
            elif token_data.get("error") not in ["authorization_pending"]:
                click.echo(
                    f"\nLogin failed or canceled: {token_data.get('error_description', 'Unknown error')}",
                    err=True,
                )
                return

    click.echo("\nLogin timed out. Please try again.", err=True)


@login.command(name="logout")
def logout():
    """Log out from GitHub and remove the stored token."""
    remove_token()


@login.command(name="status")
def login_status():
    """Check GitHub authentication status."""
    _, message = get_login_status()
    click.echo(message)
