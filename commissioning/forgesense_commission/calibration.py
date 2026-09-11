from __future__ import annotations

from dataclasses import dataclass, field
import struct
import time

from forgesense_protocol import Frame
from forgesense_stream import StreamDecoder

CALIBRATION_DIAGNOSTIC_MESSAGE_TYPE = 0x32
CAL_FLAG_TMP_SAMPLE_SEEN = 0x0001
CAL_FLAG_ADXL_SAMPLE_SEEN = 0x0002
CAL_FLAG_ADS_SAMPLE_SEEN = 0x0004
CAL_FLAG_TMP_DEVICE_OK = 0x0008
CAL_FLAG_ADXL_DEVICE_OK = 0x0010
CAL_FLAG_ADS_DEVICE_OK = 0x0020
CAL_FLAG_TMP_ERROR = 0x0040
CAL_FLAG_ADXL_ERROR = 0x0080
CAL_FLAG_ADS_ERROR = 0x0100
CAL_ALL_SAMPLE_SEEN = CAL_FLAG_TMP_SAMPLE_SEEN | CAL_FLAG_ADXL_SAMPLE_SEEN | CAL_FLAG_ADS_SAMPLE_SEEN
CAL_ALL_DEVICE_OK = CAL_FLAG_TMP_DEVICE_OK | CAL_FLAG_ADXL_DEVICE_OK | CAL_FLAG_ADS_DEVICE_OK
CAL_ANY_DEVICE_ERROR = CAL_FLAG_TMP_ERROR | CAL_FLAG_ADXL_ERROR | CAL_FLAG_ADS_ERROR
CALIBRATION_PAYLOAD_SIZE = 16


class CalibrationDiagnosticError(ValueError):
    pass


def _decode_signed24_le(data: bytes) -> int:
    if len(data) != 3:
        raise CalibrationDiagnosticError("signed24 value must contain exactly three bytes")
    value = data[0] | (data[1] << 8) | (data[2] << 16)
    if value & 0x800000:
        value -= 1 << 24
    return value


@dataclass(frozen=True)
class CalibrationDiagnosticSample:
    sequence: int
    timestamp_ms: int
    ads_ch0_raw: int
    ads_ch1_raw: int
    tmp_deci_c: int
    adxl_x_milli_g: int
    adxl_y_milli_g: int
    adxl_z_milli_g: int
    flags: int

    @property
    def temperature_c(self) -> float:
        return self.tmp_deci_c / 10.0

    @property
    def sample_set_complete(self) -> bool:
        return (self.flags & CAL_ALL_SAMPLE_SEEN) == CAL_ALL_SAMPLE_SEEN

    @property
    def devices_trusted(self) -> bool:
        return (self.flags & CAL_ALL_DEVICE_OK) == CAL_ALL_DEVICE_OK and not (self.flags & CAL_ANY_DEVICE_ERROR)

    @property
    def usable_for_calibration(self) -> bool:
        return self.sample_set_complete and self.devices_trusted

    def as_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "timestamp_ms": self.timestamp_ms,
            "ads_ch0_raw": self.ads_ch0_raw,
            "ads_ch1_raw": self.ads_ch1_raw,
            "tmp117_temperature_c": self.temperature_c,
            "tmp117_temperature_deci_c": self.tmp_deci_c,
            "adxl355_milli_g": {
                "x": self.adxl_x_milli_g,
                "y": self.adxl_y_milli_g,
                "z": self.adxl_z_milli_g,
            },
            "flags": f"0x{self.flags:04X}",
            "sample_set_complete": self.sample_set_complete,
            "devices_trusted": self.devices_trusted,
            "usable_for_calibration": self.usable_for_calibration,
        }


def decode_calibration_diagnostic(frame: Frame) -> CalibrationDiagnosticSample:
    if frame.message_type != CALIBRATION_DIAGNOSTIC_MESSAGE_TYPE:
        raise CalibrationDiagnosticError("not a calibration diagnostic frame")
    if len(frame.payload) != CALIBRATION_PAYLOAD_SIZE:
        raise CalibrationDiagnosticError("invalid calibration diagnostic payload length")

    ads_ch0_raw = _decode_signed24_le(frame.payload[0:3])
    ads_ch1_raw = _decode_signed24_le(frame.payload[3:6])
    tmp_deci_c = struct.unpack_from("<h", frame.payload, 6)[0]
    adxl_x_milli_g, adxl_y_milli_g, adxl_z_milli_g, flags = struct.unpack_from("<hhhH", frame.payload, 8)
    return CalibrationDiagnosticSample(
        sequence=frame.sequence,
        timestamp_ms=frame.timestamp_ms,
        ads_ch0_raw=ads_ch0_raw,
        ads_ch1_raw=ads_ch1_raw,
        tmp_deci_c=tmp_deci_c,
        adxl_x_milli_g=adxl_x_milli_g,
        adxl_y_milli_g=adxl_y_milli_g,
        adxl_z_milli_g=adxl_z_milli_g,
        flags=flags,
    )


def _sequence_update(candidate: int, previous: int | None) -> tuple[int | None, int, int]:
    if previous is None:
        return candidate, 0, 0
    delta = (candidate - previous) & 0xFFFF
    if delta == 0 or delta >= 0x8000:
        return previous, 0, 1
    return candidate, max(0, delta - 1), 0


@dataclass
class CalibrationDiagnosticObserver:
    max_samples: int = 4096
    decoder: StreamDecoder = field(default_factory=lambda: StreamDecoder(max_payload=256))
    frames: int = 0
    ignored_frames: int = 0
    sequence_gaps: int = 0
    sequence_faults: int = 0
    last_sequence: int | None = None
    samples: list[CalibrationDiagnosticSample] = field(default_factory=list)

    def feed(self, chunk: bytes) -> None:
        for frame in self.decoder.feed(chunk):
            if frame.message_type != CALIBRATION_DIAGNOSTIC_MESSAGE_TYPE:
                self.ignored_frames += 1
                continue
            sample = decode_calibration_diagnostic(frame)
            next_sequence, gaps, faults = _sequence_update(sample.sequence, self.last_sequence)
            self.sequence_gaps += gaps
            self.sequence_faults += faults
            self.frames += 1
            if faults:
                continue
            self.last_sequence = next_sequence
            if len(self.samples) < self.max_samples:
                self.samples.append(sample)

    @property
    def sequence_integrity_pass(self) -> bool:
        return self.sequence_gaps == 0 and self.sequence_faults == 0

    @property
    def usable_samples(self) -> list[CalibrationDiagnosticSample]:
        return [sample for sample in self.samples if sample.usable_for_calibration]

    @property
    def capture_pass(self) -> bool:
        return (
            bool(self.usable_samples)
            and self.decoder.stats.crc_or_frame_errors == 0
            and self.sequence_integrity_pass
        )

    def as_dict(self) -> dict:
        return {
            "schema": "forgesense.calibration_diagnostic_capture.v1",
            "authority": {
                "read_only": True,
                "may_control_actuators": False,
                "may_apply_calibration": False,
                "may_relax_hard_safety_limits": False,
            },
            "capture_pass": self.capture_pass,
            "frames": self.frames,
            "ignored_frames": self.ignored_frames,
            "usable_samples": len(self.usable_samples),
            "sequence_gaps": self.sequence_gaps,
            "sequence_faults": self.sequence_faults,
            "crc_or_frame_errors": self.decoder.stats.crc_or_frame_errors,
            "discarded_bytes": self.decoder.stats.discarded_bytes,
            "latest": None if not self.samples else self.samples[-1].as_dict(),
            "samples": [sample.as_dict() for sample in self.samples],
        }


def capture_calibration_diagnostics(
    transport,
    *,
    duration_s: float = 5.0,
    chunk_size: int = 128,
    max_samples: int = 4096,
) -> CalibrationDiagnosticObserver:
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if max_samples <= 0:
        raise ValueError("max_samples must be positive")

    observer = CalibrationDiagnosticObserver(max_samples=max_samples)
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        chunk = transport.read(chunk_size)
        if chunk:
            observer.feed(chunk)
    return observer
