#include "forgesense_events.h"

#include <array>
#include <cassert>
#include <iostream>

int main() {
    using namespace forgesense;

    EventRecord source{};
    source.severity = EventSeverity::Critical;
    source.source = EventSource::Edge;
    source.code = EventCode::MlCritical;
    source.sequence = 42;
    source.monotonic_ms = 123456;
    source.state_code = 3;
    source.flags = 0x01;
    source.snapshot.temperature_deci_c = 531;
    source.snapshot.vibration_milli_g = 744;
    source.snapshot.current_milli_a = 2010;
    source.snapshot.flags = kSensorAllValid;
    source.anomaly_q15 = 32000;
    source.detail = 0x11223344;

    auto encoded = encode_event_record(source);
    EventRecord decoded{};
    assert(decode_event_record(
        encoded.data(), encoded.size(), decoded) == EventDecodeStatus::Ok);
    assert(decoded.sequence == source.sequence);
    assert(decoded.monotonic_ms == source.monotonic_ms);
    assert(decoded.snapshot.temperature_deci_c == 531);
    assert(decoded.snapshot.flags == kSensorAllValid);
    assert(decoded.anomaly_q15 == 32000);
    assert(decoded.detail == 0x11223344);

    encoded[24] ^= 0x01;
    assert(decode_event_record(
        encoded.data(), encoded.size(), decoded) == EventDecodeStatus::BadCrc);

    std::cout << "firmware event record tests PASS\n";
    return 0;
}
