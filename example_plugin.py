"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EXAMPLE PLUGIN — Hexy's Bot Manager
  Open Source | Copy this file to make your own feature
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW TO REGISTER THIS FEATURE:
  Open hexys_bot_manager.py, find the FEATURES list,
  and add an entry like this:

    {
        "name":        "Example Feature",
        "description": "This is a demo plugin that logs what it receives.",
        "script":      "example_plugin.py",
        "builtin":     False,
    },

  Then the toggle button will appear in the Features panel.

HOW THIS SCRIPT IS CALLED:
  python example_plugin.py --token YOUR_BOT_TOKEN --state on|off

  sys.argv[1]  →  --token
  sys.argv[2]  →  bot token string
  sys.argv[3]  →  --state
  sys.argv[4]  →  "on" or "off"
"""

import sys
import asyncio
import discord
from discord.ext import commands

# ─── Parse arguments from Hexy's Bot Manager ──────────────────────────────────
def parse_args():
    args = sys.argv[1:]
    token = ""
    state = "off"
    for i, arg in enumerate(args):
        if arg == "--token" and i + 1 < len(args):
            token = args[i + 1]
        if arg == "--state" and i + 1 < len(args):
            state = args[i + 1]
    return token, state


# ─── Your feature logic goes here ─────────────────────────────────────────────
async def run_feature(token: str, state: str):
    """
    This is where your feature does its work.

    'state' is "on"  → feature was just enabled
    'state' is "off" → feature was just disabled

    You have full access to the bot token, so you can
    connect a second bot client, call the Discord REST API
    via requests, or do anything else you need.
    """

    print(f"[Example Plugin] State received: {state}")
    print(f"[Example Plugin] Token received: {'*' * len(token)}")  # Never print real token

    if state == "off":
        print("[Example Plugin] Feature disabled. Shutting down.")
        return

    # ── Example: connect as the bot and respond to one message ────────────────
    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"[Example Plugin] Connected as {client.user}")
        # Put your "on" logic here.
        # For a long-running feature, you'd keep the client alive.
        # For a one-shot action, close after you're done:
        await client.close()

    await client.start(token)


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    token, state = parse_args()

    if not token:
        print("[Example Plugin] ERROR: No token received. "
              "Are you launching this from Hexy's Bot Manager?")
        sys.exit(1)

    asyncio.run(run_feature(token, state))
