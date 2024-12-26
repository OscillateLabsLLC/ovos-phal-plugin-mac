"""macOS PHAL plugin for OVOS."""

import subprocess

import osascript
from ovos_bus_client import Message
from ovos_plugin_manager.phal import PHALPlugin


class MacOSPlugin(PHALPlugin):
    """macOS PHAL plugin for OVOS."""

    def __init__(self, bus=None, config=None, *args, **kwargs):
        super().__init__(bus=bus, config=config, name="ovos-PHAL-plugin-mac", *args, **kwargs)
        # System events
        self.bus.on("system.ntp.sync", self.handle_ntp_sync_request)
        self.bus.on("system.ssh.status", self.handle_ssh_status)
        self.bus.on("system.ssh.enable", self.handle_ssh_enable_request)
        self.bus.on("system.ssh.disable", self.handle_ssh_disable_request)
        self.bus.on("system.reboot", self.handle_reboot_request)
        self.bus.on("system.shutdown", self.handle_shutdown_request)
        self.bus.on("system.configure.language", self.handle_configure_language_request)
        self.bus.on("system.mycroft.service.restart", self.handle_mycroft_restart_request)
        # Volume events
        self.bus.on("mycroft.volume.get", self.handle_volume_get)
        self.bus.on("mycroft.volume.set", self.handle_volume_set)
        self.bus.on("mycroft.volume.decrease", self.handle_volume_decrease)
        self.bus.on("mycroft.volume.increase", self.handle_volume_increase)
        self.bus.on("mycroft.volume.mute", self.handle_volume_mute)
        self.bus.on("mycroft.volume.unmute", self.handle_volume_unmute)
        self.bus.on("mycroft.volume.mute.toggle", self.handle_volume_mute_toggle)

    @property
    def allow_reboot(self):
        """Check if reboot is allowed."""
        return self.config.get("allow_reboot", True)

    @property
    def allow_shutdown(self):
        """Check if shutdown is allowed."""
        return self.config.get("allow_shutdown", True)

    @property
    def volume_change_interval(self):
        """Get the volume change interval percentage. Defaults to 10."""
        return self.config.get("volume_change_interval", 10)

    def _run_command(self, command, check=True):
        """Private method to run shell commands."""
        try:
            return subprocess.run(command, check=check, capture_output=True, text=True)
        except Exception as err:
            self.log.exception("Error running command: %s", err)

    def _run_applescript(self, script):
        """Private method to run AppleScript."""
        return_code, out, err = osascript.run(script)
        self.log.debug("Return code for %s was %s", script, return_code)
        if return_code and return_code > 0:
            self.log.error("Error code %s running AppleScript: %s", return_code, err)
            return
        return out

    def _set_volume(self, volume):
        """Set the system volume (0-100)."""
        script = f"set volume output volume {volume}"
        self._run_applescript(script)

    def _get_volume(self):
        """Get the current system volume (0-100)."""
        script = "output volume of (get volume settings)"
        result = self._run_applescript(script)
        self.log.debug("Current volume: %s", result)
        return int(result) if result else None

    def _is_muted(self):
        """Check if the system is muted."""
        script = "output muted of (get volume settings)"
        result = self._run_applescript(script)
        if not result:
            return False
        return "true" in result.lower()

    def _set_mute(self, mute):
        """Set the system mute state."""
        script = "set volume with output muted"
        if not mute:
            script = "set volume without output muted"
        self._run_applescript(script)

    def handle_volume_get(self, message: Message):
        """Handle the volume get request."""
        volume = self._get_volume()
        if volume:
            self.bus.emit(message.reply("mycroft.volume.get.response", {"percent": volume}))
        else:
            self.log.error("Error getting Mac volume")

    def handle_volume_set(self, message: Message):
        """Handle the volume set request."""
        volume = message.data.get("percent", 50)
        volume = max(0, min(100, volume))  # Ensure volume is between 0 and 100
        self._set_volume(volume)
        self.bus.emit(message.forward("mycroft.volume.set.confirm", {"percent": volume}))

    def handle_volume_decrease(self, message: Message):
        """Handle the volume decrease request."""
        current_volume = self._get_volume()
        new_volume = max(
            0, current_volume - self.volume_change_interval
        )  # Decrease by volume_change_interval, but not below 0
        self._set_volume(new_volume)
        self.bus.emit(message.forward("mycroft.volume.set.confirm", {"percent": new_volume}))

    def handle_volume_increase(self, message: Message):
        """Handle the volume increase request."""
        current_volume = self._get_volume()
        new_volume = min(
            100, current_volume + self.volume_change_interval
        )  # Increase by volume_change_interval, but not above 100
        self._set_volume(new_volume)
        self.bus.emit(message.forward("mycroft.volume.set.confirm", {"percent": new_volume}))

    def handle_volume_mute(self, message: Message):
        """Handle the volume mute request."""
        self._set_mute(True)
        self.bus.emit(message.forward("mycroft.volume.mute.confirm", {"muted": True}))

    def handle_volume_unmute(self, message: Message):
        """Handle the volume unmute request."""
        self._set_mute(False)
        self.bus.emit(message.forward("mycroft.volume.mute.confirm", {"muted": False}))

    def handle_volume_mute_toggle(self, message: Message):
        """Handle the volume mute toggle request."""
        current_mute = self._is_muted()
        self._set_mute(not current_mute)
        self.bus.emit(message.forward("mycroft.volume.mute.confirm", {"muted": not current_mute}))

    def _get_ntp_server(self):
        """Private method to get the configured NTP server."""
        try:
            result = self._run_command(["systemsetup", "-getnetworktimeserver"])
            return result.stdout.strip().split(": ")[-1]
        except Exception as err:
            self.log.exception("Error getting NTP server: %s", err)
            return

    def handle_ntp_sync_request(self, message: Message):
        """Handle the NTP sync request."""
        try:
            ntp_server = self._get_ntp_server()
            self._run_command(["sntp", "-sS", ntp_server])
            self.bus.emit(message.forward("system.ntp.sync.complete"))
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.ntp.sync.failed"))

    def handle_ssh_status(self, message: Message):
        """Handle the SSH status request."""
        status = self._run_command(["systemsetup", "-getremotelogin"])
        is_enabled = "On" in status.stdout
        self.bus.emit(message.forward("system.ssh.status.response", {"enabled": is_enabled}))

    def handle_ssh_enable_request(self, message: Message):
        """Handle the SSH enable request."""
        try:
            script = """
            tell application "System Events"
                activate
                display dialog "OVOS needs Full Disk Access to enable Remote Login. Please grant permission in System Preferences." buttons {"OK"} default button "OK"
            end tell
            """
            self._run_applescript(script)
            self._run_command(["systemsetup", "-setremotelogin", "on"])
            self.bus.emit(message.forward("system.ssh.enabled"))
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.ssh.enable.failed"))

    def handle_ssh_disable_request(self, message: Message):
        """Handle the SSH disable request."""
        try:
            script = """
            tell application "System Events"
                activate
                display dialog "OVOS needs Full Disk Access to disable Remote Login. Please grant permission in System Preferences." buttons {"OK"} default button "OK"
            end tell
            """
            self._run_applescript(script)
            self._run_command(["systemsetup", "-setremotelogin", "off"])
            self.bus.emit(message.forward("system.ssh.disabled"))
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.ssh.disable.failed"))

    def handle_reboot_request(self, message: Message):
        """Handle the reboot request."""
        if self.allow_reboot is False:
            self.bus.emit(message.forward("system.reboot.failed"))
        try:
            self._run_command(["shutdown", "-r", "now"])
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.reboot.failed"))

    def handle_shutdown_request(self, message: Message):
        """Handle the shutdown request."""
        if self.allow_shutdown is False:
            self.bus.emit(message.forward("system.shutdown.failed"))
        try:
            self._run_command(["shutdown", "-h", "now"])
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.shutdown.failed"))

    def handle_configure_language_request(self, message: Message):
        """Handle the configure language request."""
        lang = message.data.get("lang")
        if lang:
            try:
                self._run_command(["defaults", "write", "NSGlobalDomain", "AppleLanguages", f'("{lang}")'])
                self.bus.emit(message.forward("system.language.configured", {"lang": lang}))
            except subprocess.CalledProcessError:
                self.bus.emit(message.forward("system.language.configure.failed"))
        else:
            self.bus.emit(message.forward("system.language.configure.failed", {"error": "Language not specified"}))

    def handle_mycroft_restart_request(self, message: Message):
        """Handle the Mycroft restart request."""
        try:
            self._run_command(["launchctl", "stop", "com.ovos.service"])
            self._run_command(["launchctl", "start", "com.ovos.service"])
            self.bus.emit(message.forward("system.mycroft.service.restarted"))
        except subprocess.CalledProcessError as err:
            self.log.exception("OVOS service request restart failed", err)
            self.bus.emit(message.forward("system.mycroft.service.restart.failed"))


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus

    plugin = MacOSPlugin(bus=FakeBus())
    print("BREAK")
