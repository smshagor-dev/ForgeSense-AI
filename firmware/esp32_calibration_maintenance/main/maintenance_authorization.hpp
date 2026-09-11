#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense::maintenance {

constexpr char kAuthorizationDomain[] =
    "ForgeSense-Calibration-Maintenance-Authorization-v1\n";
constexpr std::size_t kAuthorizationArtifactRootSize = 32;
constexpr std::size_t kAuthorizationFingerprintSize = 32;
constexpr std::size_t kAuthorizationMaxSignatureSize = 80;

class MaintenanceAuthorizationVerifier {
public:
    bool begin(const char* public_key_der_hex);
    bool ready() const;

    const std::array<std::uint8_t, kAuthorizationFingerprintSize>&
    public_key_sha256() const;

    bool verify(
        const std::array<std::uint8_t, 6>& device_mac,
        std::uint32_t expected_installed_sequence,
        const std::array<std::uint8_t, kAuthorizationArtifactRootSize>& artifact_root_sha256,
        const std::uint8_t* calibration_record,
        std::size_t calibration_record_size,
        const std::uint8_t* signature_der,
        std::size_t signature_size) const;

private:
    std::array<std::uint8_t, 256> public_key_der_{};
    std::size_t public_key_der_size_{0};
    std::array<std::uint8_t, kAuthorizationFingerprintSize> public_key_sha256_{};
    bool ready_{false};
};

}  // namespace forgesense::maintenance
