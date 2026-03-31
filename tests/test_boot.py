from pathlib import Path
from spine import Core
from conduit.boot import boot
from conduit.config import Config
from conduit.tokens import TokenStore


def test_boot_registers_config(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("[github]\nenabled = true\n")
    core = boot(config_path=toml)
    assert isinstance(core.get("config"), Config)
    assert core.get("config").github.enabled is True


def test_boot_registers_tokens(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    core = boot(config_path=toml)
    assert isinstance(core.get("tokens"), TokenStore)


def test_boot_is_frozen(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    core = boot(config_path=toml)
    assert core.is_frozen


def test_boot_once_returns_same_instance(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    c1 = boot(config_path=toml)
    c2 = boot(config_path=toml)
    assert c1 is c2


def test_instance_accessible_after_boot(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    boot(config_path=toml)
    assert Core.instance().get("config") is not None
