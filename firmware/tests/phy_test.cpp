#include "forgesense_phy.h"

#include <cassert>
#include <iostream>

int main() {
    using namespace forgesense::sensing;
    CalibrationRecord calibration{};
    calibration.temperature = {0, 1, 1, 0};
    calibration.current = {0, 1, 1, 0};

    SensorPhyReference phy(2);
    phy.set_calibration(calibration);

    auto r = phy.ingest({250, true}, {1200, true}, {3000, true});
    assert(r.temperature_update && r.temperature_deci_c == 250);
    assert(r.current_update && r.current_milli_a == 1200);
    assert(!r.vibration_update);

    r = phy.ingest({251, true}, {1210, true}, {4000, true});
    assert(r.vibration_update);
    assert(r.vibration_milli_g_rms == 3535);

    r = phy.ingest({9000000, true}, {1200, true}, {0, false});
    assert(!r.temperature_update);
    assert(r.diagnostics != 0);

    std::cout << "phy_test PASS\n";
    return 0;
}
