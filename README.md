# PHAL-plugin-mac

[![Status: Active](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/OscillateLabsLLC/.github/blob/main/SUPPORT_STATUS.md)

Provides system specific commands to OVOS for Mac OS. Creates fake ducking for OCP/ovos-media, barge-in volume adjustment, GUI button compatability, and allows for management of OVOS services.

Tested on Mac OS Sonoma 14.6.1, but should be valid for all currently supported Mac OS versions as of August 2024.

## Install

`pip install PHAL-plugin-mac`

Requires associated skill for volume-based voice commands:

- skill-ovos-volume

## Config

This plugin is not an Admin plugin, but in order for most of the system level commands to work, the user must be in the sudoers file. This can be done by running the following command in the terminal:

`sudo vim /private/etc/sudoers.d/<username>`
Replace <username> with the username of the user running the OVOS instance.

Then add the following lines to the file:

```sh
<username> ALL=(ALL) NOPASSWD: /usr/sbin/systemsetup
<username> ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
<username> ALL=(ALL) NOPASSWD: /usr/bin/sntp
<username> ALL=(ALL) NOPASSWD: /usr/bin/defaults
```

Be sure to replace `<username>` with the username of the user running the OVOS instance.

**NOTE:** Do this at your own risk. This is a security risk and should only be done if you understand the implications.

## Handle bus events to interact with the OS

### System

- `system.ntp.sync`
- `system.ssh.status`, `system.ssh.enable`, `system.ssh.disable`
- `system.reboot`, `system.shutdown`
- `system.configure.language`
- `system.mycroft.service.restart`

### Volume

- `mycroft.volume.get`, `mycroft.volume.set`
- `mycroft.volume.increase`, `mycroft.volume.decrease`
- `mycroft.volume.mute`, `mycroft.volume.unmute`, `mycroft.volume.mute.toggle`

### Display brightness

Uses the canonical OVOS PHAL brightness namespace:

- `phal.brightness.control.get` → replies with `phal.brightness.control.get.response` `{"brightness": 0..100}`
- `phal.brightness.control.set` → `{"brightness": 0..100}`, replies with `phal.brightness.control.set.confirm`
- `phal.brightness.control.sync` → re-emits `phal.brightness.control.get.response`
- `phal.brightness.control.auto.dim.update` → no-op on macOS (auto-dim is OS-managed via System Settings → Lock Screen)

> **Optional dependency:** macOS has no built-in command-line API for display
> brightness. To enable brightness handling, install the small Homebrew
> formula `brightness`:
>
> ```sh
> brew install brightness
> ```
>
> If `brightness` is not on `PATH`, the plugin still loads and the brightness
> handlers become no-ops (a warning is logged on startup). All other
> functionality is unaffected.
>
> The screenshot location can be customised via the `screenshot_dir` config
> key (default `~/Pictures`).

### Display: dark mode (Mac-specific extension)

These events are not yet part of the canonical OVOS message spec; they are
provided here so Mac users can drive macOS appearance from skills:

- `system.display.dark_mode.get` → replies with `system.display.dark_mode.get.response` `{"enabled": bool}`
- `system.display.dark_mode.set` → `{"enabled": bool}`, replies with `.set.confirm` / `.set.failed`
- `system.display.dark_mode.toggle` → flips current state, replies with `.set.confirm` / `.set.failed`

### Power & screen (Mac-specific extension)

- `system.lock` → locks the screen (`pmset displaysleepnow`); replies with `system.lock.confirm` / `system.lock.failed`
- `system.sleep` → sleeps the Mac (`pmset sleepnow`); replies with `system.sleep.confirm` / `system.sleep.failed`
- `system.screenshot` → captures the full screen via `screencapture -x`. Optional `{"path": str}`; defaults to `~/Pictures/ovos-screenshot-<timestamp>.png`. Replies with `system.screenshot.complete` `{"path": str}` / `system.screenshot.failed`

## Credits

Oscillate Labs (@mikejgray)
