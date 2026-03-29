"""Widget template registry — pre-built HTML widgets users can insert as assets."""

from fastapi import APIRouter, Depends

from app.auth import require_viewer
from app.models import ApiToken

router = APIRouter()

# ---------------------------------------------------------------------------
# Widget templates
# ---------------------------------------------------------------------------

_CLOCK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    display: flex; align-items: center; justify-content: center;
    height: 100vh; background: transparent;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }
  .clock {
    font-size: {{FONT_SIZE}};
    font-weight: 300;
    color: {{COLOR}};
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
  }
</style>
</head>
<body>
<div class="clock" id="clock"></div>
<script>
(function() {
  var format24h = {{FORMAT_24H}};
  var showSeconds = {{SHOW_SECONDS}};
  var timezone = '{{TIMEZONE}}';

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function update() {
    var opts = { hour: '2-digit', minute: '2-digit' };
    if (showSeconds) opts.second = '2-digit';
    opts.hour12 = !format24h;
    if (timezone) opts.timeZone = timezone;
    document.getElementById('clock').textContent =
      new Date().toLocaleTimeString(undefined, opts);
  }
  update();
  setInterval(update, 1000);
})();
</script>
</body>
</html>"""

_DATE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    display: flex; align-items: center; justify-content: center;
    height: 100vh; background: transparent;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }
  .date {
    font-size: {{FONT_SIZE}};
    font-weight: 300;
    color: {{COLOR}};
    text-align: center;
    line-height: 1.3;
  }
</style>
</head>
<body>
<div class="date" id="date"></div>
<script>
(function() {
  var dateFormat = '{{FORMAT}}';
  var locale = '{{LOCALE}}';

  function update() {
    var now = new Date();
    var opts;
    if (dateFormat === 'long') {
      opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    } else if (dateFormat === 'short') {
      opts = { year: 'numeric', month: 'short', day: 'numeric' };
    } else {
      opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    }
    var loc = locale || undefined;
    document.getElementById('date').textContent = now.toLocaleDateString(loc, opts);
  }
  update();
  // Update every 60 seconds — catches midnight rollover within a minute
  setInterval(update, 60000);
})();
</script>
</body>
</html>"""

_WEATHER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    display: flex; align-items: center; justify-content: center;
    height: 100vh; background: transparent;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }
  .weather {
    text-align: center; color: {{COLOR}};
  }
  .weather-icon { font-size: 4rem; margin-bottom: 0.3rem; }
  .weather-temp { font-size: {{FONT_SIZE}}; font-weight: 300; }
  .weather-desc {
    font-size: 1.4rem; opacity: 0.8; margin-top: 0.2rem;
  }
  .weather-error {
    font-size: 1.2rem; opacity: 0.6;
  }
</style>
</head>
<body>
<div class="weather" id="weather">
  <div class="weather-desc">Loading weather...</div>
</div>
<script>
(function() {
  var latitude = {{LATITUDE}};
  var longitude = {{LONGITUDE}};
  var units = '{{UNITS}}';
  var refreshMinutes = {{REFRESH_MINUTES}};

  var WMO_ICONS = {
    0: '\\u2600\\uFE0F', 1: '\\uD83C\\uDF24\\uFE0F', 2: '\\u26C5',
    3: '\\u2601\\uFE0F', 45: '\\uD83C\\uDF2B\\uFE0F', 48: '\\uD83C\\uDF2B\\uFE0F',
    51: '\\uD83C\\uDF26\\uFE0F', 53: '\\uD83C\\uDF26\\uFE0F', 55: '\\uD83C\\uDF27\\uFE0F',
    56: '\\uD83C\\uDF27\\uFE0F', 57: '\\uD83C\\uDF27\\uFE0F',
    61: '\\uD83C\\uDF26\\uFE0F', 63: '\\uD83C\\uDF27\\uFE0F', 65: '\\uD83C\\uDF27\\uFE0F',
    66: '\\uD83C\\uDF27\\uFE0F', 67: '\\uD83C\\uDF27\\uFE0F',
    71: '\\uD83C\\uDF28\\uFE0F', 73: '\\uD83C\\uDF28\\uFE0F', 75: '\\uD83C\\uDF28\\uFE0F',
    77: '\\uD83C\\uDF28\\uFE0F',
    80: '\\uD83C\\uDF26\\uFE0F', 81: '\\uD83C\\uDF27\\uFE0F', 82: '\\uD83C\\uDF27\\uFE0F',
    85: '\\uD83C\\uDF28\\uFE0F', 86: '\\uD83C\\uDF28\\uFE0F',
    95: '\\u26C8\\uFE0F', 96: '\\u26C8\\uFE0F', 99: '\\u26C8\\uFE0F'
  };
  var WMO_DESC = {
    0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
    45: 'Foggy', 48: 'Depositing rime fog',
    51: 'Light drizzle', 53: 'Moderate drizzle', 55: 'Dense drizzle',
    56: 'Freezing drizzle', 57: 'Dense freezing drizzle',
    61: 'Slight rain', 63: 'Moderate rain', 65: 'Heavy rain',
    66: 'Freezing rain', 67: 'Heavy freezing rain',
    71: 'Slight snow', 73: 'Moderate snow', 75: 'Heavy snow', 77: 'Snow grains',
    80: 'Slight showers', 81: 'Moderate showers', 82: 'Violent showers',
    85: 'Slight snow showers', 86: 'Heavy snow showers',
    95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Thunderstorm with heavy hail'
  };

  var tempUnit = units === 'fahrenheit' ? 'fahrenheit' : 'celsius';
  var unitLabel = tempUnit === 'fahrenheit' ? '\\u00B0F' : '\\u00B0C';

  function fetchWeather() {
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=' + latitude +
      '&longitude=' + longitude +
      '&current=temperature_2m,weather_code' +
      '&temperature_unit=' + tempUnit;
    fetch(url)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var c = data.current;
        var code = c.weather_code;
        var icon = WMO_ICONS[code] || '';
        var desc = WMO_DESC[code] || '';
        var temp = Math.round(c.temperature_2m);
        document.getElementById('weather').innerHTML =
          '<div class="weather-icon">' + icon + '</div>' +
          '<div class="weather-temp">' + temp + unitLabel + '</div>' +
          '<div class="weather-desc">' + desc + '</div>';
      })
      .catch(function() {
        document.getElementById('weather').innerHTML =
          '<div class="weather-error">Weather unavailable</div>';
      });
  }
  fetchWeather();
  setInterval(fetchWeather, refreshMinutes * 60 * 1000);
})();
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

WIDGETS = [
    {
        "id": "clock",
        "name": "Clock",
        "description": "Live clock that updates every second.",
        "params": [
            {"name": "FORMAT_24H", "label": "24-hour format", "type": "boolean", "default": False},
            {"name": "SHOW_SECONDS", "label": "Show seconds", "type": "boolean", "default": True},
            {"name": "TIMEZONE", "label": "Timezone (e.g. America/New_York)", "type": "string", "default": ""},
            {"name": "FONT_SIZE", "label": "Font size", "type": "string", "default": "6rem"},
            {"name": "COLOR", "label": "Text color", "type": "string", "default": "#ffffff"},
        ],
        "template": _CLOCK_HTML,
    },
    {
        "id": "date",
        "name": "Date",
        "description": "Current date, auto-updates every minute.",
        "params": [
            {"name": "FORMAT", "label": "Format (long / short)", "type": "string", "default": "long"},
            {"name": "LOCALE", "label": "Locale (e.g. en-US, de-DE)", "type": "string", "default": ""},
            {"name": "FONT_SIZE", "label": "Font size", "type": "string", "default": "3rem"},
            {"name": "COLOR", "label": "Text color", "type": "string", "default": "#ffffff"},
        ],
        "template": _DATE_HTML,
    },
    {
        "id": "weather",
        "name": "Weather",
        "description": "Current weather from Open-Meteo (free, no API key). Offline-safe fallback.",
        "params": [
            {"name": "LATITUDE", "label": "Latitude", "type": "number", "default": 40.71},
            {"name": "LONGITUDE", "label": "Longitude", "type": "number", "default": -74.01},
            {"name": "UNITS", "label": "Units (celsius / fahrenheit)", "type": "string", "default": "fahrenheit"},
            {"name": "REFRESH_MINUTES", "label": "Refresh interval (minutes)", "type": "number", "default": 15},
            {"name": "FONT_SIZE", "label": "Temperature font size", "type": "string", "default": "4rem"},
            {"name": "COLOR", "label": "Text color", "type": "string", "default": "#ffffff"},
        ],
        "template": _WEATHER_HTML,
    },
]

_WIDGET_MAP = {w["id"]: w for w in WIDGETS}


def _safe_value(val: str) -> str:
    """Sanitize a string for safe embedding in CSS property values and JS string literals."""
    val = val.replace("\\", "\\\\").replace("'", "\\'")
    val = val.replace("</", "<\\/")
    # Strip chars that could break out of CSS value contexts
    val = val.replace(";", "").replace("{", "").replace("}", "")
    return val


def _render(widget_id: str, overrides: dict | None = None) -> str:
    """Render a widget template, replacing placeholders with param values."""
    w = _WIDGET_MAP[widget_id]
    values = {p["name"]: p["default"] for p in w["params"]}
    if overrides:
        values.update(overrides)
    html = w["template"]
    for key, val in values.items():
        if isinstance(val, bool):
            html = html.replace("{{" + key + "}}", "true" if val else "false")
        else:
            html = html.replace("{{" + key + "}}", _safe_value(str(val)))
    return html


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("/widgets")
async def list_widgets(_token: ApiToken = Depends(require_viewer)):
    """Return available widget templates with rendered HTML defaults."""
    result = []
    for w in WIDGETS:
        result.append({
            "id": w["id"],
            "name": w["name"],
            "description": w["description"],
            "params": w["params"],
            "html": _render(w["id"]),
        })
    return result
