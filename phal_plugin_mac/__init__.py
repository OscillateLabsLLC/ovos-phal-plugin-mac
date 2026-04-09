"""macOS PHAL plugin for OVOS."""

import os
import shutil
import subprocess
from datetime import datetime

import osascript
from ovos_bus_client import Message
from ovos_plugin_manager.phal import PHALPlugin


class MacOSPlugin(PHALPlugin):
    """macOS PHAL plugin for OVOS."""

    def __init__(self, bus=None, config=None, *args, **kwargs):
        super().__init__(bus=bus, config=config, name="ovos-PHAL-plugin-mac", *args, **kwargs)
        for event, handler in self._handlers().items():
            self.bus.on(event, handler)

        if not self._brightness_binary_available():
            self.log.warning(
                "macOS has no built-in CLI for display brightness. "
                "Install the optional 'brightness' Homebrew formula "
                "(`brew install brightness`) to enable phal.brightness.control.* "
                "handling on this device."
            )

    def _handlers(self):
        """Return the {bus_event: handler_method} map this plugin owns.

        Subclasses can override and merge with super()._handlers() to add or
        replace events without re-stating the full list.
        """
        return {
            # System
            "system.ntp.sync": self.handle_ntp_sync_request,
            "system.ssh.status": self.handle_ssh_status,
            "system.ssh.enable": self.handle_ssh_enable_request,
            "system.ssh.disable": self.handle_ssh_disable_request,
            "system.reboot": self.handle_reboot_request,
            "system.shutdown": self.handle_shutdown_request,
            "system.configure.language": self.handle_configure_language_request,
            "system.mycroft.service.restart": self.handle_mycroft_restart_request,
            # Display: brightness (canonical PHAL events)
            "phal.brightness.control.get": self.handle_brightness_get,
            "phal.brightness.control.set": self.handle_brightness_set,
            "phal.brightness.control.sync": self.handle_brightness_sync,
            "phal.brightness.control.auto.dim.update": self.handle_brightness_auto_dim_update,
            # Display: dark mode (Mac-specific extension)
            "system.display.dark_mode.get": self.handle_dark_mode_get,
            "system.display.dark_mode.set": self.handle_dark_mode_set,
            "system.display.dark_mode.toggle": self.handle_dark_mode_toggle,
            # Power & screen (Mac-specific extension)
            "system.lock": self.handle_lock_request,
            "system.sleep": self.handle_sleep_request,
            "system.screenshot": self.handle_screenshot_request,
            # Volume
            "mycroft.volume.get": self.handle_volume_get,
            "mycroft.volume.set": self.handle_volume_set,
            "mycroft.volume.decrease": self.handle_volume_decrease,
            "mycroft.volume.increase": self.handle_volume_increase,
            "mycroft.volume.mute": self.handle_volume_mute,
            "mycroft.volume.unmute": self.handle_volume_unmute,
            "mycroft.volume.mute.toggle": self.handle_volume_mute_toggle,
        }

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

    @property
    def screenshot_dir(self):
        """Directory where screenshots are written.

        Defaults to the XDG cache location (`$XDG_CACHE_HOME/ovos/screenshots`,
        falling back to `~/.cache/ovos/screenshots`) to match other OVOS
        components and to behave correctly when the plugin runs as a
        background service rather than as the logged-in user.
        """
        configured = self.config.get("screenshot_dir")
        if configured:
            return os.path.expanduser(configured)
        xdg_cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        return os.path.join(xdg_cache, "ovos", "screenshots")

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

    # ---- Display: brightness -------------------------------------------------

    def _brightness_binary_available(self):
        """True if the optional Homebrew `brightness` CLI is on PATH."""
        return shutil.which("brightness") is not None

    def _get_brightness(self):
        """Read current display brightness as an int 0-100, or None on failure."""
        if not self._brightness_binary_available():
            return None
        result = self._run_command(["brightness", "-l"])
        if result is None or not result.stdout:
            return None
        # `brightness -l` prints lines like:
        #   display 0: brightness 0.742188
        # We take the first display we find.
        for line in result.stdout.splitlines():
            if "brightness" in line:
                try:
                    value = float(line.rsplit(" ", 1)[-1])
                    return max(0, min(100, round(value * 100)))
                except (ValueError, IndexError):
                    continue
        return None

    def _set_brightness(self, level):
        """Set the display brightness from a 0-100 percentage."""
        if not self._brightness_binary_available():
            return False
        clamped = max(0, min(100, int(level)))
        result = self._run_command(["brightness", f"{clamped / 100:.4f}"])
        return result is not None

    def handle_brightness_get(self, message: Message):
        """Handle phal.brightness.control.get."""
        level = self._get_brightness()
        if level is None:
            self.log.error("Could not read Mac display brightness")
            return
        self.bus.emit(message.reply(
            "phal.brightness.control.get.response", {"brightness": level}
        ))

    def handle_brightness_set(self, message: Message):
        """Handle phal.brightness.control.set."""
        level = message.data.get("brightness")
        if level is None:
            self.log.error("phal.brightness.control.set missing 'brightness' field")
            return
        if self._set_brightness(level):
            self.bus.emit(message.forward(
                "phal.brightness.control.set.confirm",
                {"brightness": max(0, min(100, int(level)))},
            ))

    def handle_brightness_sync(self, message: Message):
        """Handle phal.brightness.control.sync by re-emitting current level."""
        level = self._get_brightness()
        if level is None:
            return
        self.bus.emit(message.reply(
            "phal.brightness.control.get.response", {"brightness": level}
        ))

    def handle_brightness_auto_dim_update(self, message: Message):
        """Handle phal.brightness.control.auto.dim.update.

        macOS does not expose a programmatic OVOS-style auto-dim toggle from
        userland; this handler exists so the canonical event has an owner on
        Mac and so callers don't see an unhandled-event warning. The actual
        auto-dim behaviour on a Mac is controlled by the user via System
        Settings → Lock Screen.
        """
        auto_dim = message.data.get("auto_dim")
        self.log.info(
            "phal.brightness.control.auto.dim.update received (auto_dim=%s); "
            "no-op on macOS — auto-dim is managed by the OS.",
            auto_dim,
        )

    # ---- Display: dark mode --------------------------------------------------

    def _get_dark_mode(self):
        """Return True if macOS is currently in Dark mode."""
        script = (
            'tell application "System Events" to tell appearance preferences '
            'to get dark mode'
        )
        result = self._run_applescript(script)
        if result is None:
            return None
        return "true" in result.lower()

    def _set_dark_mode(self, enabled):
        """Set macOS appearance to Dark (True) or Light (False)."""
        value = "true" if enabled else "false"
        script = (
            'tell application "System Events" to tell appearance preferences '
            f'to set dark mode to {value}'
        )
        return self._run_applescript(script) is not None

    def handle_dark_mode_get(self, message: Message):
        """Handle system.display.dark_mode.get."""
        enabled = self._get_dark_mode()
        if enabled is None:
            self.log.error("Could not read Mac dark mode state")
            return
        self.bus.emit(message.reply(
            "system.display.dark_mode.get.response", {"enabled": enabled}
        ))

    def handle_dark_mode_set(self, message: Message):
        """Handle system.display.dark_mode.set."""
        enabled = bool(message.data.get("enabled", False))
        if self._set_dark_mode(enabled):
            self.bus.emit(message.forward(
                "system.display.dark_mode.set.confirm", {"enabled": enabled}
            ))
        else:
            self.bus.emit(message.forward("system.display.dark_mode.set.failed"))

    def handle_dark_mode_toggle(self, message: Message):
        """Handle system.display.dark_mode.toggle."""
        current = self._get_dark_mode()
        if current is None:
            self.bus.emit(message.forward("system.display.dark_mode.set.failed"))
            return
        new_state = not current
        if self._set_dark_mode(new_state):
            self.bus.emit(message.forward(
                "system.display.dark_mode.set.confirm", {"enabled": new_state}
            ))
        else:
            self.bus.emit(message.forward("system.display.dark_mode.set.failed"))

    # ---- Power & screen ------------------------------------------------------

    def handle_lock_request(self, message: Message):
        """Handle system.lock — lock the screen."""
        # `pmset displaysleepnow` is the most reliable way to lock the
        # screen on modern macOS without invoking GUI APIs.
        try:
            self._run_command(["pmset", "displaysleepnow"])
            self.bus.emit(message.forward("system.lock.confirm"))
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.lock.failed"))

    def handle_sleep_request(self, message: Message):
        """Handle system.sleep — put the Mac to sleep."""
        try:
            self._run_command(["pmset", "sleepnow"])
            self.bus.emit(message.forward("system.sleep.confirm"))
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.sleep.failed"))

    def handle_screenshot_request(self, message: Message):
        """Handle system.screenshot — capture the full screen to disk."""
        path = message.data.get("path")
        if not path:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = os.path.join(self.screenshot_dir, f"ovos-screenshot-{stamp}.png")
        self.log.info("Capturing screenshot to %s", path)
        try:
            # -x suppresses the camera-shutter sound.
            self._run_command(["screencapture", "-x", path])
            self.bus.emit(message.forward("system.screenshot.complete", {"path": path}))
        except subprocess.CalledProcessError:
            self.bus.emit(message.forward("system.screenshot.failed"))

    # ---- Volume --------------------------------------------------------------

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
