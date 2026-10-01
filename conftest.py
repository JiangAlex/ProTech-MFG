"""pytest configuration — pure MFG.

Collects any scripts/**/*.py that define a ``TestCase`` subclass of
ManufacturingScript with a ``run`` method, and runs it as a single item.
Loads the testbed YAML (--mfg-testbed / MFG_TESTBED) and applies the selected
SKU (--sku / MFG_SKU).
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))  # so `import mfg` works


def pytest_addoption(parser):
    parser.addoption("--mfg-testbed", default=os.environ.get("MFG_TESTBED", ""),
                     help="Manufacturing testbed YAML")
    parser.addoption("--sku", default=os.environ.get("MFG_SKU", ""),
                     help="Manufacturing SKU (selects ap.mfg.skus.<SKU> overrides)")


def pytest_collect_file(parent, file_path):
    # Collect .py under scripts/ that look like MFG test cases.
    p = Path(file_path)
    if p.suffix != ".py":
        return None
    if "scripts" not in p.parts:
        return None
    if "__pycache__" in p.parts:
        return None
    return MfgFile.from_parent(parent, path=file_path)


class MfgFile(pytest.File):
    def collect(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(self.path.stem, str(self.path))
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            return
        tc_class = getattr(module, "TestCase", None)
        if tc_class and hasattr(tc_class, "run"):
            yield MfgItem.from_parent(self, name=getattr(tc_class, "tc_id", None) or self.path.stem,
                                      tc_class=tc_class)


class MfgItem(pytest.Item):
    def __init__(self, name, parent, tc_class):
        super().__init__(name, parent)
        self.tc_class = tc_class

    def runtest(self):
        import yaml
        import re
        tc = self.tc_class()
        testbed = self.config.getoption("--mfg-testbed") or os.environ.get("MFG_TESTBED", "")
        if not testbed:
            # No explicit testbed: auto-select config/test_node/<model>_testbed.yaml
            # by the script's model. Model source priority:
            #   1) tc.model class attr (generated scripts inject it)
            #   2) the script's directory name under scripts/MFG/<MODEL>/ (hand-written)
            # Falls back to eap111 only if nothing matches. This is essential
            # because different DUTs need different testbeds (e.g. Pi7a console
            # runs at 2M baud on port 5002, EAP111 at 115200 on 5001).
            model = (getattr(tc, "model", "") or "").strip()
            if not model:
                for part in getattr(self.path, "parts", ()):
                    if part in ("EAP111", "OAP101", "Pi7a") or part.startswith(("EAP", "OAP", "Pi")):
                        model = part
                        break
            tb_dir = PROJECT_ROOT / "config" / "test_node"
            if model:
                cand = tb_dir / f"{re.sub(r'[^A-Za-z0-9]', '', model).lower()}_testbed.yaml"
                testbed = str(cand) if cand.exists() else str(tb_dir / "eap111_testbed.yaml")
            else:
                testbed = str(tb_dir / "eap111_testbed.yaml")
        if os.path.exists(testbed):
            with open(testbed) as f:
                tc.init(yaml.safe_load(f))
        sku = self.config.getoption("--sku") or os.environ.get("MFG_SKU", "")
        if sku and hasattr(tc, "set_sku"):
            tc.set_sku(sku)
        tc.run()

    def repr_failure(self, excinfo):
        return f"MFG TestCase {self.name} FAILED:\n{excinfo.value}"

    def reportinfo(self):
        return self.path, 0, f"MFG: {self.name} - {getattr(self.tc_class, 'headline', '')}"
