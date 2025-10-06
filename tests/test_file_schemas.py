from src.file_service.schemas import FileUpdateRequest
import pytest


def test_valid_tag():
    req = FileUpdateRequest(tag="Invoice_1")
    assert req.tag == "Invoice_1"


def test_invalid_tag():
    with pytest.raises(Exception):
        FileUpdateRequest(tag="_bad")

