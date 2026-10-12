"""The root modules of the Streamlit edition are shims for krinea_core.

A full copy of an engine module at the root would silently diverge from packages/core
(that already happened once): these tests fail as soon as a root name stops being the
engine module itself.
"""
import importlib
from pathlib import Path

import pytest

import krinea_core

ROOT = Path(__file__).resolve().parents[1]
SHIMS = ["biblio", "dedup", "screening", "extraction_schema"]


@pytest.mark.parametrize("name", SHIMS)
def test_root_module_is_the_engine_module(name):
    root = importlib.import_module(name)
    core = importlib.import_module(f"krinea_core.{name}")
    assert root is core
    assert Path(root.__file__).resolve().parent == Path(krinea_core.__file__).resolve().parent


def test_no_stale_copy_of_an_engine_module_at_the_root():
    engine = {p.stem for p in Path(krinea_core.__file__).parent.glob("*.py") if p.stem != "__init__"}
    for name in sorted(engine):
        path = ROOT / f"{name}.py"
        if path.exists():
            assert name in SHIMS, f"{path.name} duplicates krinea_core.{name}"
            assert f"import krinea_core.{name} as _m" in path.read_text(), f"{path.name} is not a shim"


def test_engine_data_files_are_installed():
    data = Path(krinea_core.__file__).parent / "data"
    assert (data / "energy_template.json").is_file()
    assert (data / "prisma2020_templates.json").is_file()
