from __future__ import annotations

from dataclasses import dataclass

from forgesense_protocol import Frame, ProtocolError, SOF, decode_frame

_HEADER_SIZE = 12
_CRC_SIZE = 2


@dataclass
class StreamStats:
    frames_ok: int = 0
    crc_or_frame_errors: int = 0
    discarded_bytes: int = 0
    oversize_frames: int = 0


class StreamDecoder:
    """Incremental, resynchronizing ForgeSense Link stream decoder.

    Bytes may arrive in arbitrary chunks. Garbage, malformed length fields, and
    corrupt frames are discarded without trusting the failed frame's declared
    boundary. Resynchronization always searches for the next SOF marker.
    """

    def __init__(self, *, max_payload: int = 256, max_buffer: int = 2048) -> None:
        if not 0 <= max_payload <= 0xFFFF:
            raise ValueError("max_payload out of range")
        if max_buffer < _HEADER_SIZE + _CRC_SIZE:
            raise ValueError("max_buffer too small")
        self.max_payload = max_payload
        self.max_buffer = max_buffer
        self._buffer = bytearray()
        self.stats = StreamStats()

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()

    def _discard_until_sof(self) -> bool:
        index = self._buffer.find(SOF)
        if index == -1:
            keep = 1 if self._buffer and self._buffer[-1] == SOF[0] else 0
            discard = len(self._buffer) - keep
            if discard:
                del self._buffer[:discard]
                self.stats.discarded_bytes += discard
            return False
        if index:
            del self._buffer[:index]
            self.stats.discarded_bytes += index
        return True

    def feed(self, chunk: bytes | bytearray | memoryview) -> list[Frame]:
        if chunk:
            self._buffer.extend(chunk)
        if len(self._buffer) > self.max_buffer:
            overflow = len(self._buffer) - self.max_buffer
            del self._buffer[:overflow]
            self.stats.discarded_bytes += overflow

        frames: list[Frame] = []
        while True:
            if not self._discard_until_sof():
                break
            if len(self._buffer) < _HEADER_SIZE:
                break
            payload_len = int.from_bytes(self._buffer[6:8], "little")
            if payload_len > self.max_payload:
                del self._buffer[0]
                self.stats.discarded_bytes += 1
                self.stats.oversize_frames += 1
                continue
            total = _HEADER_SIZE + payload_len + _CRC_SIZE
            if len(self._buffer) < total:
                break
            candidate = bytes(self._buffer[:total])
            try:
                frame = decode_frame(candidate)
            except ProtocolError:
                del self._buffer[0]
                self.stats.discarded_bytes += 1
                self.stats.crc_or_frame_errors += 1
                continue
            del self._buffer[:total]
            self.stats.frames_ok += 1
            frames.append(frame)
        return frames
