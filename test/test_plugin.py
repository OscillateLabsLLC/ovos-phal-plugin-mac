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


@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_set(mock_set_volume, plugin, message, bus):
    received_messages = []
    bus.on("mycroft.volume.set.confirm", lambda m: received_messages.append(m))

    message.data["percent"] = 60
    plugin.handle_volume_set(message)

    mock_set_volume.assert_called_once_with(60)
    assert len(received_messages) == 1
    assert received_messages[0].data["percent"] == 60


@patch("phal_plugin_mac.MacOSPlugin._get_volume")
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_decrease(mock_set_volume, mock_get_volume, plugin, message, bus):
    received_messages = []
    bus.on("mycroft.volume.set.confirm", lambda m: received_messages.append(m))

    mock_get_volume.return_value = 50
    plugin.handle_volume_decrease(message)

    mock_set_volume.assert_called_once_with(40)
    assert len(received_messages) == 1
    assert received_messages[0].data["percent"] == 40


@patch("phal_plugin_mac.MacOSPlugin._get_volume")
@patch("phal_plugin_mac.MacOSPlugin._set_volume")
def test_handle_volume_increase(mock_set_volume, mock_get_volume, plugin, message, bus):
    received_messages = []
    bus.on("mycroft.volume.set.confirm", lambda m: received_messages.append(m))

    mock_get_volume.return_value = 50
    plugin.handle_volume_increase(message)

    mock_set_volume.assert_called_once_with(60)
    assert len(received_messages) == 1
    assert received_messages[0].data["percent"] == 60


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
