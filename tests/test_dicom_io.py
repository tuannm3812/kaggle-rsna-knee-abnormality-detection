from pathlib import Path

import numpy as np
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from knee_mri.dicom_io import load_series


def _write_synthetic_slice(path: Path, instance_number: int, fill_value: int) -> None:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = generate_uid()
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = instance_number
    ds.Rows = 4
    ds.Columns = 4
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0

    pixels = np.full((4, 4), fill_value, dtype=np.uint16)
    ds.PixelData = pixels.tobytes()

    ds.save_as(str(path), write_like_original=False)


def test_load_series_stacks_slices_in_instance_number_order(tmp_path: Path):
    series_dir = tmp_path / "series_1"
    series_dir.mkdir()
    # Filenames deliberately sort alphabetically (a, b, c) in the opposite
    # order of their InstanceNumbers, so the assertions below only pass if
    # load_series sorts by InstanceNumber rather than trusting glob/filesystem
    # order.
    _write_synthetic_slice(series_dir / "a.dcm", instance_number=3, fill_value=30)
    _write_synthetic_slice(series_dir / "b.dcm", instance_number=1, fill_value=10)
    _write_synthetic_slice(series_dir / "c.dcm", instance_number=2, fill_value=20)

    volume = load_series(series_dir)

    assert volume.pixel_array.shape == (3, 4, 4)
    assert volume.instance_numbers == [1, 2, 3]
    assert (volume.pixel_array[0] == 10).all()
    assert (volume.pixel_array[1] == 20).all()
    assert (volume.pixel_array[2] == 30).all()


def test_load_series_raises_on_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_series"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError, match=r"No \.dcm files"):
        load_series(empty_dir)
