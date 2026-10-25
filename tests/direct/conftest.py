"""Windows stdin compatibility for genlayer-test 0.29.2, not contract mocks."""
import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def windows_stdin(monkeypatch):
    if os.name != "nt":
        return
    from gltest.direct import loader

    def inject(vm):
        from genlayer.py import calldata
        from genlayer.py.types import Address

        data = vm.get_message_raw()
        for key in ("sender_address", "origin_address", "contract_address"):
            data[key] = Address(data[key]) if isinstance(data[key], bytes) else data[key]
        data.update(entry_kind=0, entry_data=b"", entry_stage_data=None)
        with tempfile.TemporaryFile() as stream:
            stream.write(calldata.encode(data))
            stream.seek(0)
            vm._original_stdin_fd = os.dup(0)
            os.dup2(stream.fileno(), 0)

    monkeypatch.setattr(loader, "_inject_message_to_fd0", inject)
