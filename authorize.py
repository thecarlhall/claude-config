#!/usr/bin/env python3
"""
Google OAuth Token Creator
Run this once to generate token.json for headless server automation.
Covers Gmail (modify) and Drive (full access).

Usage:
    python3 authorize.py [--browser] [--client-secret PATH] [--token-out PATH]

Options:
    --browser           Open a local browser instead of the default console flow
    --client-secret     Path to your downloaded client_secret_....json file
                        (default: ~/devel/home-automation/client_secret.json)
    --token-out         Where to save the resulting token.json
                        (default: ~/.config/home-automation/token.json)
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Scopes — add more here if future skills need Calendar, Sheets, etc.
# If you add scopes, delete token.json and re-run this script.
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
]

PROJECT_DIR = os.path.expanduser("~/devel/home-automation")
DEFAULT_CLIENT_SECRET = os.path.join(PROJECT_DIR, "client_secret.json")
DEFAULT_TOKEN_OUT = os.path.expanduser("~/.config/home-automation/token.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--browser", action="store_true",
        help="Open a local browser instead of the default console flow"
    )
    parser.add_argument(
        "--client-secret", default=DEFAULT_CLIENT_SECRET, metavar="PATH",
        help=f"Path to client_secret JSON (default: {DEFAULT_CLIENT_SECRET})"
    )
    parser.add_argument(
        "--token-out", default=DEFAULT_TOKEN_OUT, metavar="PATH",
        help=f"Where to write token.json (default: {DEFAULT_TOKEN_OUT})"
    )
    return parser.parse_args()


def check_dependencies():
    missing = []
    for pkg in ("google.oauth2.credentials", "google_auth_oauthlib.flow", "google.auth.transport.requests"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg.split(".")[0].replace("_", "-"))
    if missing:
        unique = sorted(set(missing))
        print("Missing dependencies. Install them with:")
        print(f"  pip install {' '.join(unique)}")
        sys.exit(1)


def main():
    args = parse_args()
    check_dependencies()

    from google_auth_oauthlib.flow import InstalledAppFlow

    # Validate client secret file
    if not os.path.exists(args.client_secret):
        print(f"ERROR: Client secret file not found: {args.client_secret}")
        print()
        print("Steps to get it:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. APIs & Services → Credentials → Create Credentials → OAuth client ID")
        print("  3. Choose 'Desktop app', download the JSON")
        print(f"  4. Save it as: {args.client_secret}")
        sys.exit(1)

    # Ensure output directory exists
    out_dir = os.path.dirname(args.token_out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Warn if token already exists
    if os.path.exists(args.token_out):
        print(f"WARNING: {args.token_out} already exists and will be overwritten.")
        answer = input("Continue? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    print()
    print("Starting OAuth flow...")
    print("Requesting scopes:")
    for s in SCOPES:
        print(f"  {s}")
    print()

    if args.browser:
        # Local browser flow: opens browser automatically
        print("A browser window will open for you to approve access.")
        print("If it doesn't open automatically, check the terminal for a URL.")
        print()
        flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
        creds = flow.run_local_server(port=0)
    else:
        # Headless flow: print URL, open on any machine, paste code back
        # Uses out-of-band redirect — no local server needed
        flow = InstalledAppFlow.from_client_secrets_file(
            args.client_secret, SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )
        auth_url, _ = flow.authorization_url(prompt="consent")
        print("HEADLESS MODE (default)")
        print("Open this URL in any browser (e.g. on your laptop):")
        print()
        print(f"  {auth_url}")
        print()
        code = input("Paste the authorization code here: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    # Save token
    with open(args.token_out, "w") as f:
        f.write(creds.to_json())

    # Lock down permissions
    os.chmod(args.token_out, 0o600)

    print()
    print(f"✓ token.json saved to: {args.token_out}")
    print(f"✓ Permissions set to 600 (owner read/write only)")
    print()
    print("You're all set. Skills can now import google_auth.py from ~/.claude/skills/")
    print()
    print("To add more scopes later (e.g. Calendar):")
    print(f"  1. Add the scope to SCOPES in this file and in google_auth.py")
    print(f"  2. Delete {args.token_out}")
    print(f"  3. Re-run this script")


if __name__ == "__main__":
    main()
