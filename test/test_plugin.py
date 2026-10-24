# pylint: disable=missing-docstring,redefined-outer-name,protected-access,unnecessary-lambda
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from ovos_bus_client import Message
from ovos_plugin_manager.phal import find_phal_plugins
from ovos_utils.fakebus import FakeBus

from phal_plugin_mac import MacOSPlugin


@pytest.fixture
def bus():
    return FakeBus()


@pytest.fixture
def plugin(bus):
    config = {"allow_reboot": True, "allow_shutdown": True, "volume_change_interval": 10}
    return MacOSPlugin(bus=bus, config=config)


@pytest.fixture
def message():
    return Message("test.message")


def test_find_phal_plugins():
    plugins = find_phal_plugins()
    assert "ovos-phal-plugin-mac" in plugins


def test_init(plugin):
    assert plugin.allow_reboot is True
    assert plugin.allow_shutdown is True
    assert plugin.volume_change_interval == 10


def test_run_command_error(plugin):
    cmd_results = plugin._run_command(["rm", "-r", "/ae5ih7srjo8g4ege5"])
    assert not isinstance(cmd_results, subprocess.CompletedProcess)
    assert cmd_results is None


@patch("subprocess.run")
def test_get_ntp_server(mock_run, plugin):
    mock_run.return_value = MagicMock(stdout="Network Time Server: test.ntp.org\n")
    assert plugin._get_ntp_server() == "test.ntp.org"


@patch("subprocess.run")
def test_get_ntp_server_error(mock_run, plugin):
    mock_run.side_effect = subprocess.CalledProcessError(1, "test")
    assert plugin._get_ntp_server() is None


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_ssh_enable_request(mock_run_applescript, plugin, message, bus):
    received_messages = []
    bus.on("system.ssh.enabled", lambda m: received_messages.append(m))

    plugin.handle_ssh_enable_request(message)

    mock_run_applescript.assert_called()
    assert len(received_messages) == 1


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_ssh_disable_request(mock_run_applescript, plugin, message, bus):
    received_messages = []
    bus.on("system.ssh.disabled", lambda m: received_messages.append(m))

    plugin.handle_ssh_disable_request(message)

    mock_run_applescript.assert_called()
    assert len(received_messages) == 1


def test_handle_reboot_request_not_allowed(plugin, message, bus):
    plugin.config["allow_reboot"] = False
    received_messages = []
    bus.on("system.reboot.failed", lambda m: received_messages.append(m))

    plugin.handle_reboot_request(message)

    assert len(received_messages) == 1


def test_handle_shutdown_request_not_allowed(plugin, message, bus):
    plugin.config["allow_shutdown"] = False
    received_messages = []
    bus.on("system.shutdown.failed", lambda m: received_messages.append(m))

    plugin.handle_shutdown_request(message)

    assert len(received_messages) == 1


@patch.object(MacOSPlugin, "_run_command")
def test_handle_configure_language_request_error(mock_run_command, plugin, message, bus):
    mock_run_command.side_effect = subprocess.CalledProcessError(1, "language config failure")
    received_messages = []
    bus.on("system.language.configure.failed", lambda m: received_messages.append(m))

    message.data["lang"] = "en-US"
    plugin.handle_configure_language_request(message)

    assert len(received_messages) == 1
    # Optionally, check the content of the received message
    # assert received_messages[0].data == {"error": "Command execution failed"}


@patch.object(MacOSPlugin, "_run_command")
def test_handle_mycroft_restart_request_error(mock_run_command, plugin, message, bus):
    mock_run_command.side_effect = subprocess.CalledProcessError(1, "mycroft restart request error")
    received_messages = []
    bus.on("system.mycroft.service.restart.failed", lambda m: received_messages.append(m))

    plugin.handle_mycroft_restart_request(message)
    assert len(received_messages) == 1


@patch.object(MacOSPlugin, "_run_command")
def test_handle_ntp_sync_request_error(mock_run_command, plugin, message, bus):
    mock_run_command.side_effect = subprocess.CalledProcessError(1, "ntp sync request error")
    received_messages = []
    bus.on("system.ntp.sync.failed", lambda m: received_messages.append(m))

    plugin.handle_ntp_sync_request(message)

    assert len(received_messages) == 1


@patch.object(MacOSPlugin, "_run_command")
def test_handle_ssh_enable_request_error(mock_run_command, plugin, message, bus):
    mock_run_command.side_effect = subprocess.CalledProcessError(1, "ssh enable request error")
    received_messages = []
    bus.on("system.ssh.enable.failed", lambda m: received_messages.append(m))

    plugin.handle_ssh_enable_request(message)

    assert len(received_messages) == 1


@patch.object(MacOSPlugin, "_run_command")
def test_handle_ssh_disable_request_error(mock_run_command, plugin, message, bus):
    mock_run_command.side_effect = subprocess.CalledProcessError(1, "ssh disable request error")
    received_messages = []
    bus.on("system.ssh.disable.failed", lambda m: received_messages.append(m))

    plugin.handle_ssh_disable_request(message)

    assert len(received_messages) == 1


@patch("subprocess.run")
def test_run_command(mock_run, plugin):
    mock_run.return_value = MagicMock(stdout="test output")
    result = plugin._run_command(["test", "command"])
    mock_run.assert_called_once_with(["test", "command"], check=True, capture_output=True, text=True)
    assert result.stdout == "test output"


@patch("subprocess.run")
def test_run_applescript_success(mock_run, plugin):
    mock_run.return_value = MagicMock(returncode=0, stdout="50\n", stderr="")
    result = plugin._run_applescript("output volume of (get volume settings)")
    mock_run.assert_called_once_with(
        ["osascript", "-e", "output volume of (get volume settings)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result == "50"


@patch("subprocess.run")
def test_run_applescript_error_code(mock_run, plugin):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
    assert plugin._run_applescript("bogus script") is None


@patch("subprocess.run")
def test_run_applescript_exception(mock_run, plugin):
    mock_run.side_effect = OSError("osascript not found")
    assert plugin._run_applescript("set volume output volume 50") is None


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_get_volume(mock_run_applescript, plugin):
    mock_run_applescript.return_value = 50
    volume = plugin._get_volume()
    mock_run_applescript.assert_called_once_with("output volume of (get volume settings)")
    assert volume == 50


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_set_volume(mock_run_applescript, plugin):
    plugin._set_volume(75)
    mock_run_applescript.assert_called_once_with("set volume output volume 75")


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_is_muted(mock_run_applescript, plugin):
    mock_run_applescript.return_value = "true"
    assert plugin._is_muted() is True
    mock_run_applescript.assert_called_once_with("output muted of (get volume settings)")


# ---- Volume: OVOS bus speaks 0.0-1.0 fractions, AppleScript speaks 0-100 --


def _collect(bus, event):
    received = []
    bus.on(event, lambda m: received.append(m))
    return received


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_volume_get_replies_fraction_and_muted(
    mock_run_applescript, plugin, message, bus
):
    received = _collect(bus, "mycroft.volume.get.response")
    mock_run_applescript.side_effect = ["30", "true"]

    plugin.handle_volume_get(message)

    assert len(received) == 1
    assert received[0].data == {"percent": 0.3, "muted": True}


@patch("phal_plugin_mac.MacOSPlugin._is_muted", return_value=False)
@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=0)
def test_handle_volume_get_at_zero_still_replies(
    _mock_get, _mock_muted, plugin, message, bus
):
    received = _collect(bus, "mycroft.volume.get.response")

    plugin.handle_volume_get(message)

    assert len(received) == 1
    assert received[0].data == {"percent": 0.0, "muted": False}


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=None)
def test_handle_volume_get_failure_logs_and_emits_nothing(
    _mock_get, plugin, message, bus
):
    received = _collect(bus, "mycroft.volume.get.response")

    with patch.object(plugin, "log") as mock_log:
        plugin.handle_volume_get(message)

    assert received == []
    mock_log.error.assert_called_once()


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_volume_set_converts_fraction(mock_run_applescript, plugin, bus):
    received = _collect(bus, "mycroft.volume.set.confirm")

    plugin.handle_volume_set(Message("mycroft.volume.set", {"percent": 0.5}))

    mock_run_applescript.assert_called_once_with("set volume output volume 50")
    assert len(received) == 1
    assert received[0].data["percent"] == 0.5


@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_set_clamps_out_of_range(mock_set_volume, plugin, bus):
    received = _collect(bus, "mycroft.volume.set.confirm")

    with patch.object(plugin, "log") as mock_log:
        plugin.handle_volume_set(Message("mycroft.volume.set", {"percent": 1.5}))

    mock_set_volume.assert_called_once_with(100)
    mock_log.warning.assert_called_once()
    assert received[0].data["percent"] == 1.0


@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_set_defaults_to_half(mock_set_volume, plugin, message):
    plugin.handle_volume_set(message)
    mock_set_volume.assert_called_once_with(50)


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=30)
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_increase_honours_incoming_step(
    mock_set_volume, _mock_get, plugin, bus
):
    received = _collect(bus, "mycroft.volume.set.confirm")

    plugin.handle_volume_increase(Message("mycroft.volume.increase", {"percent": 0.05}))

    mock_set_volume.assert_called_once_with(35)
    assert received[0].data["percent"] == 0.35


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=50)
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_increase_uses_config_interval(
    mock_set_volume, _mock_get, plugin, message, bus
):
    received = _collect(bus, "mycroft.volume.set.confirm")

    plugin.handle_volume_increase(message)

    mock_set_volume.assert_called_once_with(60)
    assert received[0].data["percent"] == 0.6


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=95)
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_increase_clamps_at_max(
    mock_set_volume, _mock_get, plugin, message
):
    plugin.handle_volume_increase(message)
    mock_set_volume.assert_called_once_with(100)


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=50)
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_decrease_uses_config_interval(
    mock_set_volume, _mock_get, plugin, message, bus
):
    received = _collect(bus, "mycroft.volume.set.confirm")

    plugin.handle_volume_decrease(message)

    mock_set_volume.assert_called_once_with(40)
    assert received[0].data["percent"] == 0.4


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=5)
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_decrease_clamps_at_zero(mock_set_volume, _mock_get, plugin, bus):
    received = _collect(bus, "mycroft.volume.set.confirm")

    plugin.handle_volume_decrease(Message("mycroft.volume.decrease", {"percent": 0.1}))

    mock_set_volume.assert_called_once_with(0)
    assert received[0].data["percent"] == 0.0


@patch("phal_plugin_mac.MacOSPlugin._get_volume", return_value=None)
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_change_without_current_level_does_nothing(
    mock_set_volume, _mock_get, plugin, message, bus
):
    received = _collect(bus, "mycroft.volume.set.confirm")

    plugin.handle_volume_increase(message)

    mock_set_volume.assert_not_called()
    assert received == []


def test_bus_percent_round_trips_through_consumer_truncation(plugin):
    for level in range(101):
        fraction = plugin._to_bus_percent(level)
        assert 0.0 <= fraction <= 1.0
        assert int(fraction * 100) == level, f"level {level} -> {fraction!r}"
        assert plugin._from_bus_percent(fraction) == level


@patch("phal_plugin_mac.MacOSPlugin._set_mute")
def test_handle_volume_mute(mock_set_mute, plugin, message, bus):
    received_messages = []
    bus.on("mycroft.volume.mute.confirm", lambda m: received_messages.append(m))

    plugin.handle_volume_mute(message)

    mock_set_mute.assert_called_once_with(True)
    assert len(received_messages) == 1
    assert received_messages[0].data["muted"] is True


@patch("phal_plugin_mac.MacOSPlugin._set_mute")
def test_handle_volume_unmute(mock_set_mute, plugin, message, bus):
    received_messages = []
    bus.on("mycroft.volume.mute.confirm", lambda m: received_messages.append(m))

    plugin.handle_volume_unmute(message)

    mock_set_mute.assert_called_once_with(False)
    assert len(received_messages) == 1
    assert not received_messages[0].data["muted"]


@patch("phal_plugin_mac.MacOSPlugin._is_muted")
@patch("phal_plugin_mac.MacOSPlugin._set_mute")
def test_handle_volume_mute_toggle(mock_set_mute, mock_is_muted, plugin, message, bus):
    received_messages = []
    bus.on("mycroft.volume.mute.confirm", lambda m: received_messages.append(m))

    mock_is_muted.return_value = True
    plugin.handle_volume_mute_toggle(message)

    mock_set_mute.assert_called_once_with(False)
    assert len(received_messages) == 1
    assert not received_messages[0].data["muted"]


@patch("subprocess.run")
def test_handle_ntp_sync_request(mock_run, plugin, message, bus):
    received_messages = []
    bus.on("system.ntp.sync.complete", lambda m: received_messages.append(m))

    mock_run.return_value = MagicMock(stdout="Network Time Server: time.apple.com\n")
    plugin.handle_ntp_sync_request(message)

    mock_run.assert_any_call(["systemsetup", "-getnetworktimeserver"], check=True, capture_output=True, text=True)
    mock_run.assert_any_call(["sntp", "-sS", "time.apple.com"], check=True, capture_output=True, text=True)
    assert len(received_messages) == 1


@patch("subprocess.run")
def test_handle_ssh_status(mock_run, plugin, message, bus):
    received_messages = []
    bus.on("system.ssh.status.response", lambda m: received_messages.append(m))

    mock_run.return_value = MagicMock(stdout="Remote Login: On\n")
    plugin.handle_ssh_status(message)

    mock_run.assert_called_once_with(["systemsetup", "-getremotelogin"], check=True, capture_output=True, text=True)
    assert len(received_messages) == 1
    assert received_messages[0].data["enabled"] is True


@patch("subprocess.run")
def test_handle_reboot_request(mock_run, plugin, message):
    plugin.handle_reboot_request(message)
    mock_run.assert_called_once_with(["shutdown", "-r", "now"], check=True, capture_output=True, text=True)


@patch("subprocess.run")
def test_handle_shutdown_request(mock_run, plugin, message):
    plugin.handle_shutdown_request(message)
    mock_run.assert_called_once_with(["shutdown", "-h", "now"], check=True, capture_output=True, text=True)


@patch("subprocess.run")
def test_handle_configure_language_request(mock_run, plugin, message, bus):
    received_messages = []
    bus.on("system.language.configured", lambda m: received_messages.append(m))

    message.data["lang"] = "en-US"
    plugin.handle_configure_language_request(message)

    mock_run.assert_called_once_with(
        ["defaults", "write", "NSGlobalDomain", "AppleLanguages", '("en-US")'],
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(received_messages) == 1
    assert received_messages[0].data["lang"] == "en-US"


@patch("subprocess.run")
def test_handle_mycroft_restart_request(mock_run, plugin, message, bus):
    received_messages = []
    bus.on("system.mycroft.service.restarted", lambda m: received_messages.append(m))

    plugin.handle_mycroft_restart_request(message)

    mock_run.assert_any_call(["launchctl", "stop", "com.ovos.service"], check=True, capture_output=True, text=True)
    mock_run.assert_any_call(["launchctl", "start", "com.ovos.service"], check=True, capture_output=True, text=True)
    assert len(received_messages) == 1


# ---- Brightness ----------------------------------------------------------


@patch("phal_plugin_mac.shutil.which", return_value="/opt/homebrew/bin/brightness")
@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_brightness_get(mock_run_command, _mock_which, plugin, message, bus):
    received_messages = []
    bus.on("phal.brightness.control.get.response", lambda m: received_messages.append(m))

    mock_run_command.return_value = MagicMock(stdout="display 0: brightness 0.742188\n")
    plugin.handle_brightness_get(message)

    assert len(received_messages) == 1
    assert received_messages[0].data["brightness"] == 74


@patch("phal_plugin_mac.shutil.which", return_value=None)
def test_handle_brightness_get_no_binary(_mock_which, plugin, message, bus):
    received_messages = []
    bus.on("phal.brightness.control.get.response", lambda m: received_messages.append(m))

    plugin.handle_brightness_get(message)

    assert received_messages == []


@patch("phal_plugin_mac.shutil.which", return_value="/opt/homebrew/bin/brightness")
@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_brightness_set(mock_run_command, _mock_which, plugin, bus):
    received_messages = []
    bus.on("phal.brightness.control.set.confirm", lambda m: received_messages.append(m))

    mock_run_command.return_value = MagicMock(stdout="")
    msg = Message("phal.brightness.control.set", {"brightness": 60})
    plugin.handle_brightness_set(msg)

    mock_run_command.assert_called_once_with(["brightness", "0.6000"])
    assert len(received_messages) == 1
    assert received_messages[0].data["brightness"] == 60


@patch("phal_plugin_mac.shutil.which", return_value="/opt/homebrew/bin/brightness")
@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_brightness_set_clamps(mock_run_command, _mock_which, plugin, bus):
    mock_run_command.return_value = MagicMock(stdout="")
    msg = Message("phal.brightness.control.set", {"brightness": 250})
    plugin.handle_brightness_set(msg)
    mock_run_command.assert_called_once_with(["brightness", "1.0000"])


def test_handle_brightness_auto_dim_update_is_noop(plugin, message):
    # Should not raise; behaviour is purely informational on macOS.
    message.data["auto_dim"] = True
    plugin.handle_brightness_auto_dim_update(message)


# ---- Dark mode -----------------------------------------------------------


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_dark_mode_get(mock_run_applescript, plugin, message, bus):
    received_messages = []
    bus.on("system.display.dark_mode.get.response", lambda m: received_messages.append(m))

    mock_run_applescript.return_value = "true"
    plugin.handle_dark_mode_get(message)

    assert len(received_messages) == 1
    assert received_messages[0].data["enabled"] is True


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_dark_mode_set(mock_run_applescript, plugin, bus):
    received_messages = []
    bus.on("system.display.dark_mode.set.confirm", lambda m: received_messages.append(m))

    mock_run_applescript.return_value = ""
    msg = Message("system.display.dark_mode.set", {"enabled": True})
    plugin.handle_dark_mode_set(msg)

    assert len(received_messages) == 1
    assert received_messages[0].data["enabled"] is True
    # Confirm the AppleScript carries the literal "true".
    args, _ = mock_run_applescript.call_args
    assert "set dark mode to true" in args[0]


@patch("phal_plugin_mac.MacOSPlugin._run_applescript")
def test_handle_dark_mode_toggle(mock_run_applescript, plugin, message, bus):
    received_messages = []
    bus.on("system.display.dark_mode.set.confirm", lambda m: received_messages.append(m))

    # First call (get) returns "false", second call (set) returns "" (success).
    mock_run_applescript.side_effect = ["false", ""]
    plugin.handle_dark_mode_toggle(message)

    assert len(received_messages) == 1
    assert received_messages[0].data["enabled"] is True


# ---- Lock / sleep / screenshot ------------------------------------------


@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_lock_request(mock_run_command, plugin, message, bus):
    received_messages = []
    bus.on("system.lock.confirm", lambda m: received_messages.append(m))

    plugin.handle_lock_request(message)

    mock_run_command.assert_called_once_with(["pmset", "displaysleepnow"])
    assert len(received_messages) == 1


@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_sleep_request(mock_run_command, plugin, message, bus):
    received_messages = []
    bus.on("system.sleep.confirm", lambda m: received_messages.append(m))

    plugin.handle_sleep_request(message)

    mock_run_command.assert_called_once_with(["pmset", "sleepnow"])
    assert len(received_messages) == 1


@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_screenshot_request_default_path(mock_run_command, plugin, message, bus, tmp_path):
    received_messages = []
    bus.on("system.screenshot.complete", lambda m: received_messages.append(m))

    plugin.config["screenshot_dir"] = str(tmp_path)
    plugin.handle_screenshot_request(message)

    assert len(received_messages) == 1
    path = received_messages[0].data["path"]
    assert path.startswith(str(tmp_path))
    assert path.endswith(".png")
    mock_run_command.assert_called_once()
    args, _ = mock_run_command.call_args
    assert args[0][:2] == ["screencapture", "-x"]
    assert args[0][2] == path


@patch("phal_plugin_mac.MacOSPlugin._run_command")
def test_handle_screenshot_request_explicit_path(mock_run_command, plugin, bus, tmp_path):
    received_messages = []
    bus.on("system.screenshot.complete", lambda m: received_messages.append(m))

    target = str(tmp_path / "shot.png")
    msg = Message("system.screenshot", {"path": target})
    plugin.handle_screenshot_request(msg)

    mock_run_command.assert_called_once_with(["screencapture", "-x", target])
    assert received_messages[0].data["path"] == target
