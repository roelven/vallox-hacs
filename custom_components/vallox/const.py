"""Constants for the Vallox integration."""

from datetime import timedelta

from vallox_websocket_api import Profile as VALLOX_PROFILE

DOMAIN = "vallox"
DEFAULT_NAME = "Vallox"

STATE_SCAN_INTERVAL = timedelta(seconds=60)

# Common metric keys and (default) values.
METRIC_KEY_MODE = "A_CYC_MODE"
METRIC_KEY_PROFILE_FAN_SPEED_HOME = "A_CYC_HOME_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_AWAY = "A_CYC_AWAY_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_BOOST = "A_CYC_BOOST_SPEED_SETTING"

MODE_ON = 0
MODE_OFF = 5

DEFAULT_FAN_SPEED_HOME = 50
DEFAULT_FAN_SPEED_AWAY = 25
DEFAULT_FAN_SPEED_BOOST = 65

I18N_KEY_TO_VALLOX_PROFILE = {
    "home": VALLOX_PROFILE.HOME,
    "away": VALLOX_PROFILE.AWAY,
    "boost": VALLOX_PROFILE.BOOST,
    "fireplace": VALLOX_PROFILE.FIREPLACE,
    "extra": VALLOX_PROFILE.EXTRA,
    "auto": VALLOX_PROFILE.AUTO,
}

VALLOX_PROFILE_TO_PRESET_MODE = {
    VALLOX_PROFILE.HOME: "Home",
    VALLOX_PROFILE.AWAY: "Away",
    VALLOX_PROFILE.BOOST: "Boost",
    VALLOX_PROFILE.FIREPLACE: "Fireplace",
    VALLOX_PROFILE.EXTRA: "Extra",
    VALLOX_PROFILE.AUTO: "Auto",
}

PRESET_MODE_TO_VALLOX_PROFILE = {
    value: key for (key, value) in VALLOX_PROFILE_TO_PRESET_MODE.items()
}

VALLOX_CELL_STATE_TO_STR = {
    0: "Heat Recovery",
    1: "Cool Recovery",
    2: "Bypass",
    3: "Defrosting",
}

# Heating-control mode (A_CYC_SUPPLY_HEATING_ADJUST_MODE) enum.
ADJUST_MODE_SUPPLY = 0
ADJUST_MODE_EXTRACT = 1
ADJUST_MODE_COOLING = 2
ADJUST_MODE_TO_STR = {
    ADJUST_MODE_SUPPLY: "supply",
    ADJUST_MODE_EXTRACT: "extract",
    ADJUST_MODE_COOLING: "cooling",
}
ADJUST_MODE_STR_TO_VALUE = {v: k for k, v in ADJUST_MODE_TO_STR.items()}

# Nocturnal cooling service names + the register values they write.
SERVICE_START_NOCTURNAL_COOLING = "start_nocturnal_cooling"
SERVICE_STOP_NOCTURNAL_COOLING = "stop_nocturnal_cooling"

HEATING_SEASON_SETPOINT = "A_CYC_POST_HEATER_WINTER_SETPOINT"
AWAY_AIR_TEMP_TARGET = "A_CYC_AWAY_AIR_TEMP_TARGET"

# Night (cooling) values: low enough that the unit keeps the bypass open on a
# cool summer night and delivers near-outdoor-temperature supply air.
COOLING_HEATING_SEASON_SETPOINT = 5.0
COOLING_AWAY_TARGET = 8.0

# Commissioned baseline restored by stop_nocturnal_cooling.
COMMISSIONED_HEATING_SEASON_SETPOINT = 15.0
COMMISSIONED_AWAY_TARGET = 20.0

# The vallox_websocket_api client uses a hardcoded value of 65535 to
# represent an indefinite duration.
PROFILE_DURATION_INDEFINITE = 65535
