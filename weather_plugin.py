"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Weather Plugin — Hexy's Bot Manager
  /weather with global city autocomplete
  Powered by Open-Meteo (free, no API key required)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ─── Bootstrap dependencies ───────────────────────────────────────────────────
import sys
import subprocess
import importlib

for _mod, _pkg in {"discord": "discord.py", "aiohttp": "aiohttp"}.items():
    try:
        importlib.import_module(_mod)
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", _pkg, "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

# ─── Imports ──────────────────────────────────────────────────────────────────
import os
import json
import asyncio
import traceback
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands

# ─── Paths ────────────────────────────────────────────────────────────────────
PLUGIN_DIR = Path(__file__).parent
STATE_FILE = PLUGIN_DIR / "weather_state.json"
PID_FILE   = PLUGIN_DIR / "weather_plugin.pid"
LOG_FILE   = PLUGIN_DIR / "weather_plugin.log"   # ← all errors written here

# ─── Logger (writes to file since terminal is minimized) ──────────────────────
def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ─── WMO weather codes ────────────────────────────────────────────────────────
WMO = {
    0:  ("Clear Sky",                 "☀️"),
    1:  ("Mainly Clear",              "🌤️"),
    2:  ("Partly Cloudy",             "⛅"),
    3:  ("Overcast",                  "☁️"),
    45: ("Foggy",                     "🌫️"),
    48: ("Rime Fog",                  "🌫️"),
    51: ("Light Drizzle",             "🌦️"),
    53: ("Moderate Drizzle",          "🌦️"),
    55: ("Heavy Drizzle",             "🌧️"),
    61: ("Slight Rain",               "🌧️"),
    63: ("Moderate Rain",             "🌧️"),
    65: ("Heavy Rain",                "🌧️"),
    71: ("Slight Snowfall",           "❄️"),
    73: ("Moderate Snowfall",         "❄️"),
    75: ("Heavy Snowfall",            "❄️"),
    80: ("Slight Rain Showers",       "🌦️"),
    81: ("Moderate Rain Showers",     "🌦️"),
    82: ("Violent Rain Showers",      "⛈️"),
    95: ("Thunderstorm",              "⛈️"),
    96: ("Thunderstorm + Hail",       "⛈️"),
    99: ("Thunderstorm + Heavy Hail", "⛈️"),
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def wind_dir(deg: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg / 22.5) % 16]

def uv_label(uv: float) -> str:
    if uv < 3:  return f"{uv:.1f} — Low"
    if uv < 6:  return f"{uv:.1f} — Moderate"
    if uv < 8:  return f"{uv:.1f} — High"
    if uv < 11: return f"{uv:.1f} — Very High"
    return f"{uv:.1f} — Extreme ⚠️"

def vis_label(m: float) -> str:
    km = m / 1000
    if km >= 10: return f"{km:.0f} km (Excellent)"
    if km >= 5:  return f"{km:.1f} km (Good)"
    if km >= 2:  return f"{km:.1f} km (Moderate)"
    return f"{km:.1f} km (Poor)"

def temp_colour(c: float) -> discord.Colour:
    if c >= 35: return discord.Colour.from_rgb(220, 50,  50)
    if c >= 25: return discord.Colour.from_rgb(230, 140, 30)
    if c >= 15: return discord.Colour.from_rgb(240, 200, 40)
    if c >= 5:  return discord.Colour.from_rgb(80,  160, 220)
    return             discord.Colour.from_rgb(140, 210, 255)

# ─── State helpers ────────────────────────────────────────────────────────────
def read_state() -> bool:
    try:
        return json.loads(STATE_FILE.read_text()).get("active", True)
    except Exception:
        return True

def write_state(active: bool):
    STATE_FILE.write_text(json.dumps({"active": active}))

def write_pid():
    PID_FILE.write_text(str(os.getpid()))

def clear_pid():
    try: PID_FILE.unlink()
    except Exception: pass

# ─── Geocoding — sync, runs in thread executor ────────────────────────────────
def _geocode_sync(query: str, count: int = 25) -> list[dict]:
    try:
        qs = urllib.parse.urlencode({
            "name": query, "count": count,
            "language": "en", "format": "json",
        })
        req = urllib.request.Request(
            f"https://geocoding-api.open-meteo.com/v1/search?{qs}",
            headers={"User-Agent": "HexysWeatherPlugin/1.0"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            log(f"Geocode '{query}' → {len(results)} result(s)")
            return results
    except Exception:
        log(f"Geocode error:\n{traceback.format_exc()}")
        return []

async def geocode(query: str, count: int = 25) -> list[dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _geocode_sync, query, count)

# ─── Weather fetch ────────────────────────────────────────────────────────────
async def fetch_weather(lat: float, lon: float, tz: str = "auto") -> dict | None:
    params = {
        "latitude": lat, "longitude": lon, "timezone": tz,
        "current": ",".join([
            "temperature_2m","relative_humidity_2m","apparent_temperature",
            "precipitation","weather_code","surface_pressure",
            "wind_speed_10m","wind_direction_10m","wind_gusts_10m",
            "visibility","uv_index","cloud_cover","dew_point_2m",
        ]),
        "daily": ",".join([
            "temperature_2m_max","temperature_2m_min","precipitation_sum",
            "weather_code","sunrise","sunset",
        ]),
        "forecast_days": 3,
    }
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=8)
        ) as s:
            async with s.get(
                "https://api.open-meteo.com/v1/forecast", params=params
            ) as r:
                if r.status != 200:
                    log(f"Weather API returned {r.status}")
                    return None
                return await r.json()
    except Exception:
        log(f"Weather fetch error:\n{traceback.format_exc()}")
        return None

# ─── Build embed ──────────────────────────────────────────────────────────────
def build_embed(city: dict, data: dict) -> discord.Embed:
    cur = data.get("current", {})
    day = data.get("daily",   {})

    temp   = cur.get("temperature_2m",         "?")
    feels  = cur.get("apparent_temperature",   "?")
    hum    = cur.get("relative_humidity_2m",   "?")
    wspd   = cur.get("wind_speed_10m",         "?")
    wdir   = cur.get("wind_direction_10m",       0)
    gusts  = cur.get("wind_gusts_10m",         "?")
    press  = cur.get("surface_pressure",       "?")
    vis_m  = cur.get("visibility",            None)
    uv     = cur.get("uv_index",              None)
    code   = cur.get("weather_code",             0)
    cloud  = cur.get("cloud_cover",            "?")
    dew    = cur.get("dew_point_2m",           "?")
    precip = cur.get("precipitation",            0)

    wmo_label, emoji = WMO.get(int(code), ("Unknown", "🌡️"))

    parts    = [city.get("name",""), city.get("admin1",""), city.get("country","")]
    location = ", ".join(p for p in parts if p)
    colour   = temp_colour(float(temp)) if isinstance(temp, (int, float)) \
               else discord.Colour.blurple()

    embed = discord.Embed(
        title     = f"{emoji}  Weather in {location}",
        colour    = colour,
        timestamp = datetime.now(timezone.utc),
    )
    embed.add_field(name="🌡️  Temperature",
                    value=f"**{temp}°C**  (feels like {feels}°C)", inline=True)
    embed.add_field(name="🌤️  Condition",
                    value=f"{emoji} {wmo_label}", inline=True)
    embed.add_field(name="💧  Humidity",
                    value=f"{hum}%", inline=True)

    dir_str = wind_dir(float(wdir)) if isinstance(wdir, (int, float)) else "—"
    embed.add_field(name="💨  Wind",
                    value=f"{wspd} km/h {dir_str}\nGusts: {gusts} km/h", inline=True)
    embed.add_field(name="🔵  Pressure",
                    value=f"{press} hPa", inline=True)
    embed.add_field(name="☁️  Cloud Cover",
                    value=f"{cloud}%", inline=True)

    if vis_m is not None:
        embed.add_field(name="👁️  Visibility",
                        value=vis_label(float(vis_m)), inline=True)
    if uv is not None:
        embed.add_field(name="☀️  UV Index",
                        value=uv_label(float(uv)), inline=True)

    embed.add_field(name="🌫️  Dew Point",
                    value=f"{dew}°C", inline=True)
    embed.add_field(name="🌧️  Precipitation",
                    value=f"{precip} mm", inline=True)

    # 3-day forecast
    dates    = day.get("time",               [])
    hi_list  = day.get("temperature_2m_max", [])
    lo_list  = day.get("temperature_2m_min", [])
    d_codes  = day.get("weather_code",       [])
    sunrises = day.get("sunrise",            [])
    sunsets  = day.get("sunset",             [])

    lines = []
    for i in range(min(3, len(dates))):
        lbl     = "Today" if i == 0 else ("Tomorrow" if i == 1 else dates[i])
        d_emoji = WMO.get(d_codes[i], ("?","🌡️"))[1]
        lines.append(f"**{lbl}** {d_emoji}  ↑{hi_list[i]}°C  ↓{lo_list[i]}°C")
    if lines:
        embed.add_field(name="📅  3-Day Forecast",
                        value="\n".join(lines), inline=False)

    if sunrises and sunsets:
        try:
            sr = datetime.fromisoformat(sunrises[0]).strftime("%H:%M")
            ss = datetime.fromisoformat(sunsets[0]).strftime("%H:%M")
            embed.add_field(name="🌅  Sunrise / Sunset",
                            value=f"↑ {sr}  ·  ↓ {ss}  (local time)",
                            inline=False)
        except Exception:
            pass

    embed.set_footer(
        text=f"📍 {city.get('latitude','?')}°, {city.get('longitude','?')}°"
             f"  •  Open-Meteo  •  Hexy's Bot Manager"
    )
    return embed

# ─── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)

# Shared state — updated by the background poller task
_active = True

async def state_poller():
    """Polls weather_state.json every 3 seconds to detect toggle changes."""
    global _active
    while True:
        try:
            _active = read_state()
        except Exception:
            pass
        await asyncio.sleep(3)

# ─── /weather command ─────────────────────────────────────────────────────────
@tree.command(
    name="weather",
    description="Get live weather for any city in the world.",
)
@app_commands.describe(
    city="Start typing a city name — pick from the dropdown"
)
async def weather_command(interaction: discord.Interaction, city: str):
    log(f"/weather called by {interaction.user} with city='{city}'")

    # Hint placeholder — user didn't pick a real city yet
    if city == "__hint__" or "|" not in city:
        await interaction.response.send_message(
            "❌  Please **pick a city from the dropdown** rather than typing manually.",
            ephemeral=True,
        )
        return

    # Feature disabled
    if not _active:
        embed = discord.Embed(
            title="❌  Weather Feature Disabled",
            description=(
                "The **Weather** feature has been turned off by the administrator.\n"
                "Ask them to re-enable it in **Hexy's Bot Manager**."
            ),
            colour=discord.Colour.from_rgb(180, 40, 60),
        )
        embed.set_footer(text="Hexy's Bot Manager")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    # Decode the pipe-delimited value from autocomplete
    # Format: "City, Region, Country|lat|lon|tz"
    try:
        parts     = city.split("|")
        name_part = parts[0]
        lat       = float(parts[1])
        lon       = float(parts[2])
        tz        = parts[3] if len(parts) > 3 else "auto"
        segs      = [s.strip() for s in name_part.split(",")]
        city_dict = {
            "name":      segs[0],
            "admin1":    segs[1] if len(segs) > 2 else "",
            "country":   segs[-1] if len(segs) > 1 else "",
            "latitude":  lat,
            "longitude": lon,
        }
        log(f"Parsed: {city_dict['name']}, lat={lat}, lon={lon}, tz={tz}")
    except Exception:
        log(f"Failed to parse city value: {city}\n{traceback.format_exc()}")
        await interaction.followup.send(
            "❌  Could not parse that city. Please pick from the dropdown.",
            ephemeral=True,
        )
        return

    data = await fetch_weather(lat, lon, tz)
    if not data:
        await interaction.followup.send(
            "❌  Weather data unavailable right now. Please try again.",
            ephemeral=True,
        )
        return

    try:
        embed = build_embed(city_dict, data)
        await interaction.followup.send(embed=embed)
    except Exception:
        log(f"Embed build/send error:\n{traceback.format_exc()}")
        await interaction.followup.send(
            "❌  Something went wrong displaying the weather. Check weather_plugin.log.",
            ephemeral=True,
        )

# ─── Autocomplete ─────────────────────────────────────────────────────────────
@weather_command.autocomplete("city")
async def city_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    # Wrap EVERYTHING in try/except — any uncaught exception here
    # causes "Loading options failed" on Discord's side
    try:
        log(f"Autocomplete called: current='{current}'")

        if len(current) < 2:
            return [
                app_commands.Choice(
                    name="Start typing a city name to search worldwide…",
                    value="__hint__",
                )
            ]

        try:
            results = await asyncio.wait_for(
                geocode(current, count=25),
                timeout=2.5,
            )
        except asyncio.TimeoutError:
            log(f"Autocomplete timed out for '{current}'")
            return []

        choices: list[app_commands.Choice] = []

        for r in results:
            try:
                name    = str(r.get("name",      "") or "")
                admin1  = str(r.get("admin1",    "") or "")
                country = str(r.get("country",   "") or "")
                lat     = r.get("latitude",   0.0)
                lon     = r.get("longitude",  0.0)
                tz      = str(r.get("timezone", "auto") or "auto")
                pop     = r.get("population")

                # Build human-readable label for the dropdown
                label_parts = [x for x in [name, admin1, country] if x]
                if pop and isinstance(pop, int):
                    label_parts.append(f"pop. {pop:,}")
                label = ", ".join(label_parts)

                # Build the pipe-delimited value string
                display = ", ".join(x for x in [name, admin1, country] if x)
                value   = f"{display}|{lat}|{lon}|{tz}"

                # Discord hard-limits both to 100 chars
                if len(label) > 100:
                    label = label[:97] + "…"
                if len(value) > 100:
                    value = f"{name}|{lat}|{lon}|{tz}"
                if len(value) > 100:
                    value = f"{name[:30]}|{lat}|{lon}|{tz}"

                choices.append(app_commands.Choice(name=label, value=value))
            except Exception:
                log(f"Error building choice for result {r}:\n{traceback.format_exc()}")
                continue

        log(f"Returning {len(choices)} choice(s) for '{current}'")
        return choices[:25]

    except Exception:
        # This catches anything we missed — must never propagate to discord.py
        log(f"UNHANDLED autocomplete error:\n{traceback.format_exc()}")
        return []

# ─── Tree error handler ───────────────────────────────────────────────────────
@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    log(f"App command error: {error}\n{traceback.format_exc()}")
    try:
        await interaction.response.send_message(
            f"❌  An error occurred: {error}", ephemeral=True
        )
    except Exception:
        pass

# ─── Client events ────────────────────────────────────────────────────────────
@client.event
async def on_ready():
    global _active
    _active = read_state()
    log(f"Logged in as {client.user}  ({client.user.id})")
    log(f"In {len(client.guilds)} guild(s)")

    # Sync to every guild right now for instant availability
    for guild in client.guilds:
        try:
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            log(f"Synced to guild: {guild.name}")
        except Exception:
            log(f"Guild sync failed for {guild.name}:\n{traceback.format_exc()}")

    # Global sync (covers guilds the bot joins later — up to 1 hour)
    try:
        synced = await tree.sync()
        log(f"Global sync: {len(synced)} command(s)")
    except Exception:
        log(f"Global sync error:\n{traceback.format_exc()}")

    # Start state poller
    asyncio.create_task(state_poller())
    log("State poller started. Ready!")
    log(f"Feature active: {_active}")

# ─── Entry point ──────────────────────────────────────────────────────────────
def parse_args() -> tuple[str, str]:
    args  = sys.argv[1:]
    token = ""
    state = "on"
    for i, a in enumerate(args):
        if a == "--token" and i + 1 < len(args): token = args[i + 1]
        if a == "--state" and i + 1 < len(args): state = args[i + 1]
    return token, state


def main():
    token, state = parse_args()

    if not token:
        log("ERROR: No token. Launch via Hexy's Bot Manager.")
        sys.exit(1)

    write_state(state == "on")

    if state == "off":
        log("State → OFF. Running instance will notice within 3 seconds.")
        return

    if PID_FILE.exists():
        log(f"Already running (PID {PID_FILE.read_text().strip()}). State → ON.")
        return

    write_pid()
    import atexit
    atexit.register(clear_pid)

    log("=" * 50)
    log("Weather Plugin starting…")
    log(f"Log file: {LOG_FILE}")
    log("=" * 50)

    try:
        client.run(token, log_handler=None)
    except discord.LoginFailure:
        log("ERROR: Invalid token.")
    except Exception:
        log(f"Fatal error:\n{traceback.format_exc()}")
    finally:
        clear_pid()


if __name__ == "__main__":
    main()
