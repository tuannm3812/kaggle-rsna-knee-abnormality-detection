"""DICOM series loading: decode all slices in a series directory into a
stacked volume, sorted by InstanceNumber."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom


@dataclass
class SeriesVolume:
    """A decoded DICOM series: stacked pixel data plus its slice order."""

    pixel_array: np.ndarray  # shape (num_slices, rows, cols)
    instance_numbers: list[int]


def load_series(series_dir: Path) -> SeriesVolume:
    """Load every `.dcm` file in `series_dir` into a single stacked volume.

    Slices are sorted by `InstanceNumber` so the stack order matches
    acquisition order regardless of filesystem listing order. Relies on
    `pydicom`'s pixel data handlers (with the `dicom-extra` optional
    dependency group installed) to decode all four transfer syntaxes the
    competition data uses: uncompressed Explicit VR Little Endian, JPEG
    Lossless, JPEG 2000, and Implicit VR Little Endian.

    Args:
        series_dir: Directory containing one series' `.dcm` slice files.

    Returns:
        A `SeriesVolume` with slices stacked along axis 0 in acquisition
        order.

    Raises:
        FileNotFoundError: If `series_dir` contains no `.dcm` files.
    """
    dcm_paths = sorted(series_dir.glob("*.dcm"))
    if not dcm_paths:
        raise FileNotFoundError(f"No .dcm files found in {series_dir}")

    datasets = [pydicom.dcmread(path) for path in dcm_paths]
    datasets.sort(key=lambda ds: int(ds.InstanceNumber))

    pixel_array = np.stack([ds.pixel_array for ds in datasets], axis=0)
    instance_numbers = [int(ds.InstanceNumber) for ds in datasets]

    return SeriesVolume(pixel_array=pixel_array, instance_numbers=instance_numbers)
