
# Pawfit Home Assistant Integration

**⚠️ UNOFFICIAL INTEGRATION - NOT SUPPORTED BY PAWFIT ⚠️**

A community-built Home Assistant integration for Pawfit pet trackers. Track multiple dogs/pets and integrate their location data into your smart home automations.

## ⚠️ CRITICAL SETUP REQUIREMENT ⚠️

**🚨 DO NOT USE YOUR MAIN PAWFIT ACCOUNT WITH THIS INTEGRATION! 🚨**

You **MUST** create a separate Pawfit account for this integration. If you use your main account, you will be repeatedly logged out of the mobile app whenever the integration updates, potentially causing you to lose track of your pet in an emergency!

### Required Setup Steps:

1. **Create a NEW Pawfit account** with a different email address
2. **Share your pets** from your main account to this new account
3. **Log into the NEW account** on your mobile app
4. **Accept the pet sharing invitation** in the new account
5. **Log back into your MAIN account** on your mobile app
6. **Use the NEW account credentials** when setting up this integration in Home Assistant

This ensures your main mobile app stays logged in while the integration uses the secondary account.

## Features

- 📍 **GPS Device Tracker** - Track your pets' real-time location on the Home Assistant map
- 🔋 **Battery Monitoring** - Monitor battery level and charging status
- 📶 **Signal Strength** - View GPS signal quality
- 🎯 **Location Accuracy** - See GPS accuracy in meters
- 🕐 **Last Seen** - Track when location was last updated
- � **Find Mode** - Activate GPS tracking for 10 minutes with button and status sensor
- 💡 **Light Mode** - Turn on tracker LED light for 10 minutes with button and status sensor
- 🚨 **Alarm Mode** - Activate tracker alarm for 10 minutes with button and status sensor
- ⏱️ **Timer Sensors** - View countdown timers for active modes
- �🐕 **Multiple Pets** - Support for multiple trackers under one account
- 🏠 **Home Assistant Integration** - Use in automations, scripts, and dashboards

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu (⋮) in the top right corner
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/dansbaker/homeassistant-pawfit`
6. Select category: "Integration"
7. Click "Add"
8. Search for "Pawfit" in HACS integrations
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download this repository
2. Copy the `custom_components/pawfit` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Pawfit"
3. Enter your **NEW** Pawfit account credentials (not your main account!)
4. Complete the setup

## Available Entities

For each tracker, the integration provides:

### Device Tracker
- GPS location with accuracy and battery level

### Sensors
- Battery level (%)
- Signal strength
- Location accuracy (meters)
- Last seen timestamp
- Find mode timer (countdown in seconds)
- Light mode timer (countdown in seconds)
- Alarm mode timer (countdown in seconds)

### Binary Sensors
- Charging status
- Find mode active (10-minute duration)
- Light mode active (10-minute duration)
- Alarm mode active (10-minute duration)

### Buttons
- Find mode toggle (activate/deactivate GPS tracking)
- Light mode toggle (activate/deactivate LED light)
- Alarm mode toggle (activate/deactivate alarm sound)

Each mode runs for exactly 10 minutes when activated. You can deactivate early by pressing the button again.

## Beta Status

🚧 **This is BETA software with expanding features.**

Current limitations:
- Limited tracker commands (Find, Light, and Alarm modes only)
- Basic location and status information
- No advanced Pawfit features (geofences, activity tracking, etc.)

## Support & Feature Requests

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/dansbaker/homeassistant-pawfit/issues)
- 💡 **Feature Requests**: [GitHub Issues](https://github.com/dansbaker/homeassistant-pawfit/issues)
- ❓ **Questions**: [GitHub Discussions](https://github.com/dansbaker/homeassistant-pawfit/discussions)

## Disclaimer

This integration is:
- **Unofficial** and not affiliated with Pawfit
- **Community-developed** and maintained
- **Based on reverse engineering** of the Pawfit mobile app API
- **Use at your own risk** - the API may change without notice

## License

[Apache 2.0](LICENSE)
