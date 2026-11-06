import numpy as np
import pytest

from app.contracts import (
    BURNING_T_U8,
    T_U8_MAX,
    T_U8_MIN,
    Scene,
    quantize_beta,
    quantize_T,
)
from app.protocol import HEADER_SIZE, pack_frame, unpack_frame

# Shared with frontend/src/core/protocol.test.ts.
GOLDEN_HEX = "07000000" "0000c03f" "0300" "0200" "01000000" "000102030405" "fffefdfcfbfa"


def golden_fields() -> tuple[np.ndarray, np.ndarray]:
    T = np.arange(6, dtype=np.uint8).reshape(2, 3)
    beta = (255 - np.arange(6)).astype(np.uint8).reshape(2, 3)
    return T, beta


def test_header_is_16_bytes():
    assert HEADER_SIZE == 16


def test_pack_matches_golden_bytes():
    T, beta = golden_fields()
    assert pack_frame(7, 1.5, T, beta).hex() == GOLDEN_HEX


def test_roundtrip():
    rng = np.random.default_rng(0)
    T = rng.integers(0, 256, (40, 60), dtype=np.uint8)
    beta = rng.integers(0, 256, (40, 60), dtype=np.uint8)
    f = unpack_frame(pack_frame(123, 4.25, T, beta))
    assert (f.frame, f.t) == (123, 4.25)
    np.testing.assert_array_equal(f.T, T)
    np.testing.assert_array_equal(f.beta, beta)


def test_pack_accepts_non_contiguous_views():
    T = np.zeros((4, 6), dtype=np.uint8)
    T[:, ::2] = 9
    view = T[:, ::2]
    f = unpack_frame(pack_frame(0, 0.0, view, view))
    np.testing.assert_array_equal(f.T, view)


def test_pack_rejects_bad_input():
    T, beta = golden_fields()
    with pytest.raises(TypeError):
        pack_frame(0, 0.0, T.astype(np.float32), beta)
    with pytest.raises(ValueError):
        pack_frame(0, 0.0, T, beta[:1])


def test_unpack_rejects_truncated_buffer():
    data = bytes.fromhex(GOLDEN_HEX)
    with pytest.raises(ValueError):
        unpack_frame(data[:-1])


def test_quantization_range():
    T = np.array([T_U8_MIN - 100, T_U8_MIN, T_U8_MAX, T_U8_MAX + 100])
    np.testing.assert_array_equal(quantize_T(T), [0, 0, 255, 255])
    np.testing.assert_array_equal(quantize_beta(np.array([-0.1, 0.0, 0.5, 1.0])), [0, 0, 128, 255])
    assert 0 < BURNING_T_U8 < 255


def test_scene_coerces_and_validates():
    s = Scene(heightmap=np.zeros((10, 20)), cell_size=2.0, trees=np.zeros((0, 4)))
    assert s.heightmap.dtype == np.float32
    assert (s.nx, s.ny, s.width, s.depth) == (20, 10, 40.0, 20.0)
    with pytest.raises(ValueError):
        Scene(heightmap=np.zeros(5), cell_size=1.0, trees=np.zeros((0, 4)))
