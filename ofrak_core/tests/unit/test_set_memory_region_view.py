"""Pin the dotted view-type paths the GUI "Set Memory Region" action posts as the add_view
`view_type`. SetMemoryRegionView.svelte hardcodes these strings; if a Python rename breaks them the
GUI action silently fails, so a rename must break this test too."""
import importlib


def test_set_memory_region_view_dotted_paths_importable():
    for module_path, cls_name in (
        ("ofrak.core.code_region", "CodeRegion"),
        ("ofrak.core.memory_region", "MemoryRegion"),
    ):
        module = importlib.import_module(module_path)
        assert hasattr(module, cls_name)
