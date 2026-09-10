#include "forgesense_sensor_contract_generated.h"

#include <cassert>
#include <iostream>

int main() {
    using namespace forgesense::sensor_contract;
    static_assert(kVersion == 1);
    static_assert(kTemperatureMinDeciC == -400);
    static_assert(kTemperatureMaxDeciC == 1250);
    static_assert(kVibrationMaxMilliG == 16000);
    static_assert(kCurrentMaxMilliA == 20000);
    static_assert(kSnapshotRateHz == 10);
    assert(kTemperatureStaleMs > kVibrationStaleMs);
    std::cout << "sensor_contract_test PASS\n";
    return 0;
}
