import struct
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.util import find_spec
from itertools import chain
from typing import Any

from app.ai.exceptions import AIProviderError, AIResponseError
from app.core.messages import AIMessages

MP3_ENCODER_MODULE = "lameenc"
MP3_BIT_RATE_KBPS = 64
MP3_ENCODER_QUALITY = 5
PCM_FORMAT_TAG = 1
PCM_SAMPLE_BYTES = 2
RIFF_HEADER_BYTES = 12
CHUNK_HEADER_BYTES = 8
FMT_BODY_LAYOUT = "<HHIIHH"
FMT_BODY_BYTES = struct.calcsize(FMT_BODY_LAYOUT)


@dataclass(frozen=True)
class PcmFormat:
    sample_rate: int
    channels: int


def _malformed() -> AIResponseError:
    return AIResponseError(AIMessages.MALFORMED_RESPONSE)


def _parse_fmt(body: bytes) -> PcmFormat:
    format_tag, channels, sample_rate, _, _, bits = struct.unpack(
        FMT_BODY_LAYOUT, body[:FMT_BODY_BYTES]
    )
    if format_tag != PCM_FORMAT_TAG or bits != PCM_SAMPLE_BYTES * 8 or channels < 1:
        raise _malformed()
    return PcmFormat(sample_rate, channels)


def parse_wav_header(buffer: bytes) -> tuple[PcmFormat, int] | None:
    if len(buffer) < RIFF_HEADER_BYTES:
        return None
    if buffer[:4] != b"RIFF" or buffer[8:12] != b"WAVE":
        raise _malformed()
    offset = RIFF_HEADER_BYTES
    pcm_format: PcmFormat | None = None
    while len(buffer) >= offset + CHUNK_HEADER_BYTES:
        chunk_id = buffer[offset : offset + 4]
        (size,) = struct.unpack("<I", buffer[offset + 4 : offset + CHUNK_HEADER_BYTES])
        body_start = offset + CHUNK_HEADER_BYTES
        if chunk_id == b"data":
            if pcm_format is None:
                raise _malformed()
            return pcm_format, body_start
        body_end = body_start + size
        if len(buffer) < body_end + (size & 1):
            return None
        if chunk_id == b"fmt ":
            pcm_format = _parse_fmt(buffer[body_start:body_end])
        offset = body_end + (size & 1)
    return None


def _read_header(chunks: Iterator[bytes]) -> tuple[PcmFormat, bytes]:
    buffer = b""
    for chunk in chunks:
        buffer += chunk
        parsed = parse_wav_header(buffer)
        if parsed is not None:
            pcm_format, data_start = parsed
            return pcm_format, buffer[data_start:]
    raise _malformed()


def ensure_mp3_encoder_available() -> None:
    if find_spec(MP3_ENCODER_MODULE) is None:
        raise AIProviderError(AIMessages.MP3_ENCODER_MISSING)


def _build_encoder(pcm_format: PcmFormat) -> Any:
    import lameenc

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(MP3_BIT_RATE_KBPS)
    encoder.set_in_sample_rate(pcm_format.sample_rate)
    encoder.set_channels(pcm_format.channels)
    encoder.set_quality(MP3_ENCODER_QUALITY)
    return encoder


def wav_stream_to_mp3(chunks: Iterator[bytes]) -> Iterator[bytes]:
    pcm_format, first_pcm = _read_header(chunks)
    encoder = _build_encoder(pcm_format)
    frame_bytes = pcm_format.channels * PCM_SAMPLE_BYTES
    remainder = b""
    for block in chain([first_pcm], chunks):
        data = remainder + block
        usable = len(data) - len(data) % frame_bytes
        remainder = data[usable:]
        encoded = encoder.encode(data[:usable])
        if encoded:
            yield bytes(encoded)
    tail = encoder.flush()
    if tail:
        yield bytes(tail)
