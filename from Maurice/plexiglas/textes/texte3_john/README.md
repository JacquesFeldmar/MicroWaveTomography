# Technical package for John

- report_john.tex / report_john.pdf: English report.
- figures/: vector plots and edited presentation photo.
- data/: calibrated complex means in CSV and Touchstone (Hz, real/imaginary, 50 ohms). No window or background subtraction has been applied to these exports.
- data/manifest.json: source acquisition paths and sweep counts.
- build_figures.py: regenerates figures and peak table from the accompanying CSV files using NumPy, SciPy and Matplotlib.

This package uses the available 9 October 2026 blue-antenna measurements (50, 60, 70 cm), not the unavailable 22 September raw files. The old results are explicitly identified as historical in the report.

Plate dimensions remain unspecified and should be supplied before sending if available. All physical distances are approximate.

Rebuild from this directory:

    python build_figures.py
    pdflatex -interaction=nonstopmode -halt-on-error report_john.tex
    pdflatex -interaction=nonstopmode -halt-on-error report_john.tex

The setup_edited.png image was made using the built-in image-generation tool. Its background was replaced and the original apparatus was requested to be preserved. It is illustrative, not a metrological record.
