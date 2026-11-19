"""
Image comparison for matplotlib figures

``compare_figure(fig, "name")`` saves the figure to
``tests/result_images/<test_module>/name.png`` and compares it with
``tests/baseline_images/<test_module>/name.png``. Run
``pytest --update-baselines`` to write new baselines.
"""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pytest
from matplotlib.testing.compare import compare_images

TOLERANCE = 2
tests_dir = Path(__file__).parent
_UPDATE = False


def pytest_addoption(parser):
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="Write result images as the new baselines",
    )


def pytest_configure(config):
    global _UPDATE
    _UPDATE = config.getoption("--update-baselines")
    mpl.use("Agg")


@pytest.fixture(autouse=True)
def _mpl_defaults():
    mpl.rcdefaults()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "text.hinting": "auto",
            "text.antialiased": True,
            "figure.dpi": 72,
            "savefig.dpi": 72,
        }
    )
    yield
    plt.close("all")


@pytest.fixture
def compare_figure():
    def compare(fig, name: str):
        test_file = inspect.stack()[1][1]
        sub = Path(test_file).stem
        base = tests_dir / "baseline_images" / sub / f"{name}.png"
        result = tests_dir / "result_images" / sub / f"{name}.png"
        expected = result.with_name(f"{name}-expected.png")
        result.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(result)
        if _UPDATE:
            base.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result, base)
        if not base.exists():
            raise AssertionError(f"Baseline image {base} is missing")
        shutil.copyfile(base, expected)
        err = compare_images(str(expected), str(result), TOLERANCE, in_decorator=True)
        assert not err, (
            "images not close: {actual} vs. {expected} (RMS {rms:.2f})".format(**err)
        )

    return compare
