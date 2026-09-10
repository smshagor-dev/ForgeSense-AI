#include "telemetry_publisher.hpp"

#include "sdkconfig.h"

#include <array>
#include <cstdio>

namespace forgesense::edge {

bool TelemetryPublisher::maybe_publish(std::uint32_t now_ms, bool force) {
#if CONFIG_FORGESENSE_TELEMETRY_ENABLE
    if (!force && have_published_ &&
        (now_ms - last_publish_ms_) < CONFIG_FORGESENSE_TELEMETRY_PERIOD_MS) {
        return true;
    }

    std::array<char, kDeviceTelemetryMaxLine> line{};
    const std::size_t size = snapshot_.encode_line(now_ms, line.data(), line.size());
    if (size == 0) {
        return false;
    }
    if (std::fwrite(line.data(), 1, size, stdout) != size) {
        return false;
    }
    std::fflush(stdout);
    last_publish_ms_ = now_ms;
    have_published_ = true;
#else
    (void)now_ms;
    (void)force;
#endif
    return true;
}

}  // namespace forgesense::edge
