from pathlib import Path

from forgesense_ml.export_cpp import render_cpp_reference_header
from forgesense_ml.reference import fit_reference_model


def test_committed_cpp_reference_model_is_reproducible() -> None:
    expected = render_cpp_reference_header(fit_reference_model())
    committed = Path(
        "firmware/components/forgesense_inference/include/"
        "forgesense_reference_model_generated.h"
    ).read_text(encoding="utf-8")
    assert committed == expected
