#include "forgesense_calibration.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense::sensing;
    CalibrationRecord record{};
    record.sequence = 42;
    record.temperature = {100, 2, 5, -30};
    record.current = {-50, 3, 2, 10};

    std::array<std::uint8_t, kCalibrationBlobSize> blob{};
    assert(encode_calibration_record(record, blob));
    CalibrationRecord decoded{};
    assert(decode_calibration_record(blob.data(), blob.size(), decoded));
    assert(decoded.sequence == 42);
    assert(decoded.temperature.raw_zero == 100);
    assert(decoded.current.gain_numerator == 3);

    auto corrupt = blob;
    corrupt[20] ^= 0x55;
    assert(!decode_calibration_record(corrupt.data(), corrupt.size(), decoded));

    record.current.gain_denominator = 0;
    assert(!encode_calibration_record(record, blob));

    std::cout << "calibration_test PASS\n";
    return 0;
}
