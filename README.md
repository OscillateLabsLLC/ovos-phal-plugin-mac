# PHAL-plugin-mac

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

```python
# System
self.bus.on("system.ntp.sync", self.handle_ntp_sync_request)
self.bus.on("system.ssh.status", self.handle_ssh_status)
self.bus.on("system.ssh.enable", self.handle_ssh_enable_request)
self.bus.on("system.ssh.disable", self.handle_ssh_disable_request)
self.bus.on("system.reboot", self.handle_reboot_request)
self.bus.on("system.shutdown", self.handle_shutdown_request)
self.bus.on("system.configure.language", self.handle_configure_language_request)
self.bus.on("system.mycroft.service.restart", self.handle_mycroft_restart_request)
# Volume
self.bus.on("mycroft.volume.get", self.handle_volume_set)
self.bus.on("mycroft.volume.set", self.handle_volume_set)
self.bus.on("mycroft.volume.decrease", self.handle_volume_decrease)
self.bus.on("mycroft.volume.increase", self.handle_volume_increase)
self.bus.on("mycroft.volume.mute", self.handle_volume_mute)
self.bus.on("mycroft.volume.unmute", self.handle_volume_unmute)
self.bus.on("mycroft.volume.mute.toggle", self.handle_volume_mute_toggle)
```

## Credits

Oscillate Labs (@mikejgray)
