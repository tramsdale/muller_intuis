# Muller Intuis Home Assistant Integration

A comprehensive Home Assistant integration for Muller Intuis heating systems, providing seamless control of climate, water heaters, and energy monitoring.

## Features

### 🌡️ Climate Control
- **Room-based climate entities** with individual temperature control
- **Multiple HVAC modes**: Heat, Auto, Off
- **Frost Protection (ECO preset)** - Set rooms to frost protection mode (7°C minimum)
- **Real-time temperature monitoring** - Current and target temperatures
- **Automatic mode detection** - Manual, scheduled, and frost protection modes

### 🚿 Water Heater Control
- **Dedicated water heater entities** for hot water management
- **Three operation modes**: Off, Auto, Force-on
- **Module-based control** - Direct API calls to water heater modules (NMW type)
- **Bridge-aware communication** - Proper routing through Zigbee bridges
- **Status monitoring** - Real-time contactor mode and boiler status

### ⚡ Energy Monitoring
- **Room-based energy statistics** for both heating and hot water
- **Cumulative energy tracking** with proper counter reset handling
- **Home Assistant Energy Dashboard integration**
- **Historical data backfilling** - Automatic statistics synchronization
- **Dual statistics support** - Both hourly consumption and cumulative totals

### 🏠 System Features
- **Automatic device discovery** - Detects rooms, modules, and device types
- **OAuth2 authentication** with automatic token refresh (1-hour expiry)
- **Real-time status updates** - 30-second polling for responsive control
- **Robust error handling** - Comprehensive logging and error recovery
- **Bridge ID support** - Proper module communication routing

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the "+" button
4. Search for "Muller Intuis"
5. Install the integration
6. Restart Home Assistant

### Manual Installation
1. Copy the `muller_intuis` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration → Integrations
4. Click "Add Integration"
5. Search for "Muller Intuis"

## Configuration

### UI Configuration (Recommended)
1. Go to **Configuration** → **Integrations**
2. Click **"Add Integration"**
3. Search for **"Muller Intuis"**
4. Enter your credentials:
   - **Username**: Your Muller Intuis account username
   - **Password**: Your Muller Intuis account password
   - **Client ID**: Your API client ID
   - **Client Secret**: Your API client secret
   - **Base URL**: `https://app.muller-intuitiv.net` (default)

### YAML Configuration
Add to your `configuration.yaml`:

```yaml
muller_intuis:
  username: your_username
  password: your_password
  client_id: your_client_id
  client_secret: your_client_secret
  base_url: https://app.muller-intuitiv.net  # Optional
```

## Entities Created

### Climate Entities
- **Entity ID**: `climate.{room_name}`
- **Features**: Temperature control, HVAC modes, ECO preset for frost protection
- **Attributes**: Current temperature, target temperature, HVAC action

### Water Heater Entities
- **Entity ID**: `water_heater.{room_name}_water_heater`
- **Operation Modes**: Off, Auto, Force On
- **Attributes**: Current operation, availability status

### Energy Statistics
- **Heating Energy**: `muller_intuis:muller_intuis_energy_{home_id}_{room_id}`
- **Hot Water Energy**: `muller_intuis:muller_intuis_hot_water_energy_{home_id}_{room_id}`
- **Integration**: Automatic Home Assistant Energy Dashboard integration

## Device Types Supported

### Climate Modules
- **NMH**: Room heating modules with temperature control
- **FPN**: Muller type designation for heating devices

### Water Heater Modules
- **NMW**: Water heater controller modules
- **NWH**: Alternative water heater module type

### Bridge Modules
- **NMG**: Main gateway/router modules
- **NMR**: Zigbee bridge modules for device communication

## API Integration

### Authentication
- **OAuth2 flow** with automatic token management
- **1-hour token expiry** with automatic refresh
- **Secure credential storage** in Home Assistant

### Data Coordination
- **Configuration data**: One-time fetch of home structure and devices
- **Status updates**: Real-time polling every 30 seconds
- **Energy data**: Historical measurements every hour

### API Endpoints Used
- `/oauth2/token` - Authentication and token refresh
- `/api/homesdata` - Home configuration and device structure
- `/syncapi/v1/homestatus` - Real-time room and module status
- `/syncapi/v1/setstate` - Climate and water heater control
- `/api/gethomemeasure` - Historical energy measurements

## Services

### Climate Services
- `climate.set_temperature` - Set target temperature
- `climate.set_hvac_mode` - Change HVAC mode (heat/auto/off)
- `climate.set_preset_mode` - Enable frost protection (ECO preset)

### Water Heater Services
- `water_heater.set_operation_mode` - Change water heater mode

## Troubleshooting

### Common Issues

#### Authentication Errors
```
ERROR: Authentication failed
```
**Solution**: Verify username, password, client ID, and client secret

#### Module Detection Issues
```
WARNING: No water heater module found for room
```
**Solution**: Check device logs for module types and bridge assignments

#### Energy Data Gaps
```
WARNING: Large negative energy contribution detected
```
**Solution**: Integration now handles counter resets automatically

### Debug Logging
Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.muller_intuis: debug
```

### Bridge ID Issues
If water heater controls fail:
1. Check that bridge IDs are detected for NMW modules
2. Verify bridge connectivity in module status
3. Review API call structure includes proper bridge routing

## Development

### Architecture
```
muller_intuis/
├── __init__.py              # Integration setup and platform loading
├── config_flow.py           # UI configuration flow
├── const.py                 # Constants and configuration
├── coordinator.py           # Data update coordinators
├── models.py                # Data models and API response parsing
├── muller_intuisAPI.py      # API client implementation
├── climate.py               # Climate platform
├── water_heater.py          # Water heater platform
├── sensor.py                # Energy statistics handling
└── manifest.json            # Integration metadata
```

### Key Classes
- **MullerIntuisConfigCoordinator**: One-time configuration data
- **MullerIntuisDataUpdateCoordinator**: Real-time status updates
- **MullerIntuisEnergyCoordinator**: Historical energy data
- **MullerIntuisEnergyStatisticsHandler**: Energy dashboard integration

### API Client Features
- **Automatic token refresh** - Handles 1-hour token expiry
- **Bridge-aware communication** - Routes commands through proper bridges
- **Error handling** - Comprehensive exception management
- **Cache management** - Intelligent data caching and invalidation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Code Style
- Follow Home Assistant development guidelines
- Use `ruff` for code formatting and linting
- Include comprehensive logging
- Write docstrings for all methods

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Community support and questions
- **Documentation**: Additional documentation on the Home Assistant community

## Changelog

### Latest Version
- ✅ **Climate Control**: Full HVAC mode support with frost protection
- ✅ **Water Heater Control**: Three-mode operation with bridge routing
- ✅ **Energy Monitoring**: Cumulative statistics with counter reset handling
- ✅ **OAuth2 Authentication**: Automatic token management
- ✅ **Device Discovery**: Automatic room and module detection
- ✅ **Bridge Support**: Proper module communication routing

### Previous Versions
- Initial climate platform implementation
- Basic API authentication
- Energy sensor prototype

---

**Made with ❤️ for the Home Assistant community**