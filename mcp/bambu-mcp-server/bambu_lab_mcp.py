"""Bambu Lab P1P MCP Server

This MCP server enables LLMs to interact with Bambu Lab P1P 3D printers via MQTT.
It provides tools for checking printer status, controlling prints, and monitoring progress.

Required environment variables:
    BAMBU_PRINTER_IP: IP address of your printer (e.g., "192.168.1.100")
    BAMBU_ACCESS_CODE: Access code from printer settings (Network → LAN Mode → Access Code)
    BAMBU_SERIAL_NUMBER: Serial number of your printer (e.g., "01P00A123456789")
"""

import asyncio
import json
import os
import ssl
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# Module-level constants
CHARACTER_LIMIT = 25000
MQTT_PORT = 8883
MQTT_USERNAME = "bblp"
MQTT_QOS = 0

# State management for printer status
printer_state: Dict[str, Any] = {}
mqtt_client: Optional[mqtt.Client] = None
connection_ready = asyncio.Event()


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class PrintCommand(str, Enum):
    """Available print control commands."""
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


# === MQTT Connection Management ===


def get_mqtt_client() -> mqtt.Client:
    """Get or create the MQTT client singleton."""
    global mqtt_client
    if mqtt_client is None:
        mqtt_client = setup_mqtt_client()
    return mqtt_client


def setup_mqtt_client() -> mqtt.Client:
    """Initialize and configure MQTT client with TLS."""
    printer_ip = os.getenv("BAMBU_PRINTER_IP")
    access_code = os.getenv("BAMBU_ACCESS_CODE")
    serial_number = os.getenv("BAMBU_SERIAL_NUMBER")

    if not all([printer_ip, access_code, serial_number]):
        raise ValueError(
            "Missing required environment variables: BAMBU_PRINTER_IP, "
            "BAMBU_ACCESS_CODE, and BAMBU_SERIAL_NUMBER must be set"
        )

    client = mqtt.Client(client_id="bambu_mcp_client")
    client.username_pw_set(MQTT_USERNAME, access_code)

    # Configure TLS
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    # Set up callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Connect to printer
    client.connect(printer_ip, MQTT_PORT, keepalive=60)
    client.loop_start()

    return client


def on_connect(client: mqtt.Client, userdata: Any, flags: Dict, rc: int) -> None:
    """Callback for when client connects to MQTT broker."""
    if rc == 0:
        serial_number = os.getenv("BAMBU_SERIAL_NUMBER")
        # Subscribe to printer status reports
        client.subscribe(f"device/{serial_number}/report", qos=MQTT_QOS)
        connection_ready.set()
        print(f"Connected to Bambu Lab printer {serial_number}")
    else:
        print(f"Failed to connect to printer, return code: {rc}")


def on_disconnect(client: mqtt.Client, userdata: Any, rc: int) -> None:
    """Callback for when client disconnects from MQTT broker."""
    connection_ready.clear()
    print(f"Disconnected from printer, return code: {rc}")


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """Callback for when a message is received from the printer."""
    try:
        payload = json.loads(msg.payload.decode())
        # Update printer state with the latest data
        if "print" in payload:
            printer_state.update(payload["print"])
    except json.JSONDecodeError:
        print(f"Failed to decode message: {msg.payload}")


async def ensure_connection() -> None:
    """Ensure MQTT connection is ready before operations."""
    await asyncio.wait_for(connection_ready.wait(), timeout=10.0)


async def request_full_status() -> None:
    """Request full printer status update."""
    client = get_mqtt_client()
    serial_number = os.getenv("BAMBU_SERIAL_NUMBER")

    command = {
        "pushing": {
            "sequence_id": "0",
            "command": "pushall"
        }
    }

    client.publish(
        f"device/{serial_number}/request",
        json.dumps(command),
        qos=1
    )

    # Wait a bit for the response
    await asyncio.sleep(2.0)


# === Formatting Helpers ===


def format_print_stage(stage: str) -> str:
    """Convert print stage code to human-readable string."""
    stages = {
        "-1": "Idle",
        "0": "Printing",
        "1": "Auto bed leveling",
        "2": "Heatbed preheating",
        "3": "Sweeping XY mech mode",
        "4": "Changing filament",
        "5": "M400 pause",
        "6": "Paused due to filament runout",
        "7": "Heating hotend",
        "8": "Calibrating extrusion",
        "9": "Scanning bed surface",
        "10": "Inspecting first layer",
        "11": "Identifying build plate type",
        "12": "Calibrating micro lidar",
        "13": "Homing toolhead",
        "14": "Cleaning nozzle tip",
        "15": "Checking extruder temperature",
        "16": "Printing was paused by the user",
        "17": "Pause of front cover falling",
        "18": "Calibrating the micro lidar",
        "19": "Calibrating extrusion flow",
        "20": "Paused due to nozzle temperature malfunction",
        "21": "Paused due to heat bed temperature malfunction"
    }
    return stages.get(str(stage), f"Unknown stage: {stage}")


def format_gcode_state(state: str) -> str:
    """Convert gcode state to human-readable string."""
    states = {
        "IDLE": "Idle",
        "PREPARE": "Preparing",
        "RUNNING": "Running",
        "PAUSE": "Paused",
        "FINISH": "Finished",
        "FAILED": "Failed"
    }
    return states.get(state, state)


def format_temperature(temp: Optional[int]) -> str:
    """Format temperature value."""
    if temp is None:
        return "N/A"
    return f"{temp}°C"


def format_status_markdown(state: Dict[str, Any]) -> str:
    """Format printer status as markdown."""
    if not state:
        return "No status data available. The printer may be offline."

    lines = ["# Bambu Lab P1P Status\n"]

    # Print status
    gcode_state = state.get("gcode_state", "UNKNOWN")
    lines.append(f"**Status:** {format_gcode_state(gcode_state)}")

    if gcode_state in ["RUNNING", "PAUSE"]:
        mc_percent = state.get("mc_percent", 0)
        lines.append(f"**Progress:** {mc_percent}%")

        # Print time information
        mc_remaining_time = state.get("mc_remaining_time", 0)
        if mc_remaining_time > 0:
            hours = mc_remaining_time // 60
            minutes = mc_remaining_time % 60
            lines.append(f"**Time Remaining:** {hours}h {minutes}m")

        # Current file
        gcode_file = state.get("gcode_file", "")
        if gcode_file:
            lines.append(f"**File:** {gcode_file}")

        # Print stage
        stg_cur = state.get("stg_cur")
        if stg_cur is not None:
            lines.append(f"**Stage:** {format_print_stage(stg_cur)}")

    # Temperatures
    lines.append("\n## Temperatures")
    nozzle_temper = state.get("nozzle_temper")
    nozzle_target = state.get("nozzle_target_temper")
    lines.append(f"- **Nozzle:** {format_temperature(nozzle_temper)} (Target: {format_temperature(nozzle_target)})")

    bed_temper = state.get("bed_temper")
    bed_target = state.get("bed_target_temper")
    lines.append(f"- **Bed:** {format_temperature(bed_temper)} (Target: {format_temperature(bed_target)})")

    # Speed and fans
    lines.append("\n## Print Settings")
    spd_lvl = state.get("spd_lvl", 2)
    speed_names = {1: "Silent", 2: "Standard", 3: "Sport", 4: "Ludicrous"}
    lines.append(f"- **Speed:** {speed_names.get(spd_lvl, 'Unknown')}")

    fan_gear = state.get("fan_gear", 0)
    lines.append(f"- **Part Cooling Fan:** {fan_gear}%")

    # Layer information
    layer_num = state.get("layer_num")
    total_layer_num = state.get("total_layer_num")
    if layer_num is not None and total_layer_num is not None:
        lines.append(f"- **Layer:** {layer_num}/{total_layer_num}")

    return "\n".join(lines)


# === MCP Server Setup ===


@asynccontextmanager
async def app_lifespan(app):
    """Manage MQTT connection lifecycle."""
    # Initialize MQTT connection
    client = get_mqtt_client()
    await ensure_connection()

    yield {"mqtt_client": client}

    # Cleanup on shutdown
    client.loop_stop()
    client.disconnect()


mcp = FastMCP("bambu_lab_mcp", lifespan=app_lifespan)


# === Tool Definitions ===


class GetStatusInput(BaseModel):
    """Input for getting printer status."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )
    detailed: bool = Field(
        default=False,
        description="If true, requests full status update from printer (may take 2-3 seconds)"
    )


@mcp.tool(
    name="bambu_get_status",
    annotations={
        "title": "Get Printer Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bambu_get_status(params: GetStatusInput) -> str:
    """Get current status of the Bambu Lab P1P printer.

    This tool retrieves the current state of the printer including print progress,
    temperatures, print stage, and other operational information. Use this to check
    if the printer is idle, printing, or in an error state before starting new prints.

    Args:
        params (GetStatusInput): Parameters containing:
            - response_format (ResponseFormat): Output format (markdown or json)
            - detailed (bool): Whether to request full status update

    Returns:
        str: Printer status in the requested format containing:
            - Print status (idle, printing, paused, finished, failed)
            - Print progress percentage (if printing)
            - Time remaining (if printing)
            - Current filename (if printing)
            - Nozzle and bed temperatures (current and target)
            - Print speed setting
            - Fan speeds
            - Layer information

    Example Usage:
        - "What's the status of my printer?"
        - "Is my print finished?"
        - "What temperature is the nozzle at?"
    """
    try:
        await ensure_connection()

        if params.detailed:
            await request_full_status()

        if params.response_format == ResponseFormat.MARKDOWN:
            return format_status_markdown(printer_state)
        else:
            return json.dumps(printer_state if printer_state else {}, indent=2)

    except asyncio.TimeoutError:
        return "Error: Could not connect to printer. Please check that the printer is powered on and connected to the network."
    except Exception as e:
        return f"Error getting printer status: {str(e)}"


class ControlPrintInput(BaseModel):
    """Input for controlling an active print."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    command: PrintCommand = Field(
        ...,
        description="Control command: 'pause' to pause print, 'resume' to continue, 'stop' to cancel"
    )


@mcp.tool(
    name="bambu_control_print",
    annotations={
        "title": "Control Active Print",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def bambu_control_print(params: ControlPrintInput) -> str:
    """Control an active print job (pause, resume, or stop).

    This tool allows you to pause, resume, or stop a print that is currently in progress.
    WARNING: The 'stop' command will cancel the print and cannot be undone. Always confirm
    with the user before stopping a print.

    Args:
        params (ControlPrintInput): Parameters containing:
            - command (PrintCommand): Control action to perform

    Returns:
        str: Confirmation message of the action taken

    Example Usage:
        - "Pause my current print"
        - "Resume the print"
        - "Stop the print" (requires user confirmation)
    """
    try:
        await ensure_connection()

        client = get_mqtt_client()
        serial_number = os.getenv("BAMBU_SERIAL_NUMBER")

        command_payload = {
            "print": {
                "sequence_id": str(int(datetime.now().timestamp())),
                "command": params.command.value,
                "param": ""
            }
        }

        client.publish(
            f"device/{serial_number}/request",
            json.dumps(command_payload),
            qos=1
        )

        return f"Successfully sent '{params.command.value}' command to printer."

    except asyncio.TimeoutError:
        return "Error: Could not connect to printer. Please check that the printer is powered on and connected to the network."
    except Exception as e:
        return f"Error controlling print: {str(e)}"


class SetSpeedInput(BaseModel):
    """Input for setting print speed."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    speed_level: int = Field(
        ...,
        description="Speed level: 1=Silent, 2=Standard, 3=Sport, 4=Ludicrous",
        ge=1,
        le=4
    )


@mcp.tool(
    name="bambu_set_speed",
    annotations={
        "title": "Set Print Speed",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bambu_set_speed(params: SetSpeedInput) -> str:
    """Change the print speed during an active print.

    This tool adjusts the print speed to one of four preset levels. Changes take effect
    immediately during an active print. Higher speeds reduce print time but may reduce
    quality. Lower speeds improve quality and reduce noise.

    Args:
        params (SetSpeedInput): Parameters containing:
            - speed_level (int): Speed preset (1-4)

    Returns:
        str: Confirmation message of speed change

    Speed Levels:
        1 - Silent: Quietest operation, slowest print
        2 - Standard: Balanced speed and quality (default)
        3 - Sport: Faster printing with good quality
        4 - Ludicrous: Maximum speed (may reduce quality)

    Example Usage:
        - "Set print speed to sport mode"
        - "Change to silent mode"
        - "Speed up the print to ludicrous"
    """
    try:
        await ensure_connection()

        client = get_mqtt_client()
        serial_number = os.getenv("BAMBU_SERIAL_NUMBER")

        speed_names = {1: "Silent", 2: "Standard", 3: "Sport", 4: "Ludicrous"}

        command_payload = {
            "print": {
                "sequence_id": str(int(datetime.now().timestamp())),
                "command": "print_speed",
                "param": str(params.speed_level)
            }
        }

        client.publish(
            f"device/{serial_number}/request",
            json.dumps(command_payload),
            qos=1
        )

        return f"Successfully set print speed to {speed_names[params.speed_level]} (level {params.speed_level})."

    except asyncio.TimeoutError:
        return "Error: Could not connect to printer. Please check that the printer is powered on and connected to the network."
    except Exception as e:
        return f"Error setting print speed: {str(e)}"


# === Main Entry Point ===

if __name__ == "__main__":
    mcp.run()
