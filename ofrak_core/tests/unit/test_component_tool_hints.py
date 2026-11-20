"""Tests for ComponentExternalTool.pip_package and the dependency install-hint rendering."""
from ofrak.component.abstract import ComponentMissingDependencyError
from ofrak.core.binwalk import BINWALK_TOOL


def test_binwalk_missing_dependency_names_pip_module():
    assert BINWALK_TOOL.pip_package == "git+https://github.com/ReFirmLabs/binwalk@v2.3.4"
    msg = str(ComponentMissingDependencyError(object(), BINWALK_TOOL))
    assert "pip install git+https://github.com/ReFirmLabs/binwalk@v2.3.4" in msg
    assert "OFRAK's Python environment" in msg
    assert "restart OFRAK" in msg


def test_missing_dependency_renders_all_declared_package_managers():
    # Table-driven rendering must show every declared manager, including choco (previously omitted).
    class _FakeComponent:
        pass

    class _FakeTool:
        tool = "frob"
        tool_homepage = "https://example.invalid/frob"
        apt_package = "frob-apt"
        brew_package = "frob-brew"
        choco_package = "frob-choco"
        pip_package = "frob-pip"

    msg = str(ComponentMissingDependencyError(_FakeComponent(), _FakeTool()))
    assert "apt install frob-apt" in msg
    assert "brew install frob-brew" in msg
    assert "choco install frob-choco" in msg
    assert "pip install frob-pip" in msg
