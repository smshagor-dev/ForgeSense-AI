#include "forgesense_sensing.h"

#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense::sensing;

    {
        LinearCalibration c{1000, 2, 5, -10};
        const auto r = calibrate_to_i16(1250, c);
        assert(r.valid);
        assert(r.value == 90);
        assert(r.diagnostics == kDiagNone);
    }
    {
        LinearCalibration c{0, 1, 0, 0};
        const auto r = calibrate_to_i16(100, c);
        assert(!r.valid);
        assert((r.diagnostics & kDiagBadCalibration) != 0);
    }
    {
        LinearCalibration c{};
        const auto r = calibrate_to_i16(9000000, c);
        assert(!r.valid);
        assert((r.diagnostics & kDiagRawOutOfRange) != 0);
    }
    {
        LinearCalibration c{0, 1000, 1, 0};
        const auto r = calibrate_to_i16(1000, c);
        assert(r.valid);
        assert(r.value == 32767);
        assert((r.diagnostics & kDiagNumericSaturation) != 0);
    }

    assert(integer_sqrt_u64(0) == 0);
    assert(integer_sqrt_u64(1) == 1);
    assert(integer_sqrt_u64(15) == 3);
    assert(integer_sqrt_u64(16) == 4);
    assert(integer_sqrt_u64(25000000ULL) == 5000);

    {
        VibrationRmsWindow rms(2);
        std::uint16_t out = 0;
        assert(!rms.ingest(3000, out));
        assert(rms.ingest(4000, out));
        assert(out == 3535);
        assert(rms.samples_collected() == 0);
    }
    {
        VibrationRmsWindow rms(4);
        std::uint16_t out = 0;
        for (int i = 0; i < 3; ++i) {
            assert(!rms.ingest(-1200, out));
        }
        assert(rms.ingest(-1200, out));
        assert(out == 1200);
    }

    std::cout << "sensing_test PASS\n";
    return 0;
}
