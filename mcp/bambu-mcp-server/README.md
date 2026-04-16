# Bambu Lab P1P MCP Server

An MCP (Model Context Protocol) server that enables Claude Desktop to interact with your Bambu Lab P1P 3D printer via MQTT. Control your printer, check status, and manage prints directly through Claude!

## Features

- **Get Printer Status**: Check print progress, temperatures, and printer state
- **Control Prints**: Pause, resume, or stop active prints
- **Adjust Speed**: Change print speed between Silent, Standard, Sport, and Ludicrous modes
- **Real-time Updates**: Monitors printer status via MQTT

## Prerequisites

- Python 3.10 or higher
- Bambu Lab P1P printer on your local network
- Printer access code (from printer settings)

## Getting Your Printer Information

You'll need three pieces of information from your P1P:

1. **Printer IP Address**: Find this in your router's DHCP client list or printer settings
2. **Access Code**: 
   - On printer screen: Settings → Network → LAN Mode
   - Enable LAN Mode if not already enabled
   - Note the 8-character access code
3. **Serial Number**: 
   - Found on printer screen: Settings → Device
   - Format: `01P00AXXXXXXXXX`

## Installation

1. **Clone or download these files** to a directory on your computer

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**. Create a `.env` file or set these in your shell:
```bash
export BAMBU_PRINTER_IP="192.168.1.100"        # Your printer's IP
export BAMBU_ACCESS_CODE="12345678"            # Your 8-char access code
export BAMBU_SERIAL_NUMBER="01P00A123456789"   # Your printer serial number
```

4. **Test the server** (optional):
```bash
python bambu_lab_mcp.py --help
```

## Claude Desktop Configuration

Add this to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "bambu-lab": {
      "command": "python",
      "args": ["/absolute/path/to/bambu_lab_mcp.py"],
      "env": {
        "BAMBU_PRINTER_IP": "192.168.1.100",
        "BAMBU_ACCESS_CODE": "12345678",
        "BAMBU_SERIAL_NUMBER": "01P00A123456789"
      }
    }
  }
}
```

**Important**: Replace `/absolute/path/to/bambu_lab_mcp.py` with the full path to where you saved the file.

## Usage Examples

Once configured, you can ask Claude things like:

- "What's the status of my 3D printer?"
- "Is my print finished?"
- "Pause my current print"
- "Resume the print"
- "Set print speed to sport mode"
- "What temperature is the nozzle at?"
- "How much time is left on the print?"

## Available Tools

### `bambu_get_status`
Get current printer status including:
- Print state (idle, printing, paused, etc.)
- Progress percentage and time remaining
- Nozzle and bed temperatures
- Current filename and layer information
- Speed settings and fan speeds

Options:
- `detailed`: Request full status update (takes 2-3 seconds)
- `response_format`: Choose 'markdown' (default) or 'json' output

### `bambu_control_print`
Control active prints:
- `pause`: Pause the current print
- `resume`: Resume a paused print
- `stop`: Cancel the print (⚠️ cannot be undone)

### `bambu_set_speed`
Change print speed during printing:
- Level 1: Silent (quietest, slowest)
- Level 2: Standard (default, balanced)
- Level 3: Sport (faster with good quality)
- Level 4: Ludicrous (maximum speed)

## Troubleshooting

### "Could not connect to printer"
- Verify printer is powered on and connected to Wi-Fi
- Check printer IP address is correct
- Ensure LAN Mode is enabled on the printer
- Verify access code is correct (case-sensitive)

### "Missing required environment variables"
- Double-check all three environment variables are set
- Verify the variable names match exactly (case-sensitive)
- Make sure values are not empty strings

### MCP Server not showing up in Claude
- Verify the path in `claude_desktop_config.json` is absolute, not relative
- Restart Claude Desktop after configuration changes
- Check Claude Desktop logs for error messages

### Permission denied on macOS/Linux
- Make sure the Python file is readable: `chmod +r bambu_lab_mcp.py`
- Verify Python is installed and accessible from the command line

## Security Notes

- The access code grants full control of your printer - keep it secure
- This server connects to your printer over your local network only
- No data is sent to external servers
- The MQTT connection uses TLS encryption

## Limitations

- Only supports one printer per server instance
- Cannot upload new files to the printer (use Bambu Studio/Handy for that)
- No camera feed access
- P1P-specific (may work with P1S/X1C but untested)

## Contributing

Feel free to submit issues or pull requests to improve this MCP server!

## License

MIT License - feel free to use and modify as needed.

## Acknowledgments

- Built using the [Model Context Protocol](https://modelcontextprotocol.io/)
- MQTT integration based on community reverse-engineering efforts
- Thanks to the Bambu Lab community for API documentation
