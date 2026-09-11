#include "maintenance_authorization.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "mbedtls/md.h"
#include "mbedtls/pk.h"

namespace forgesense::maintenance {
namespace {

constexpr std::size_t kCalibrationRecordSize = 48;
constexpr std::size_t kAuthorizationDomainSize = sizeof(kAuthorizationDomain) - 1U;
constexpr std::size_t kAuthorizationPayloadSize =
    kAuthorizationDomainSize + 6U + 4U + kAuthorizationArtifactRootSize + kCalibrationRecordSize;
constexpr std::array<std::uint8_t, 10> kPrime256v1Oid{
    0x06, 0x08, 0x2A, 0x86, 0x48, 0xCE, 0x3D, 0x03, 0x01, 0x07};

int hex_nibble(char value) {
    if (value >= '0' && value <= '9') {
        return value - '0';
    }
    if (value >= 'a' && value <= 'f') {
        return value - 'a' + 10;
    }
    if (value >= 'A' && value <= 'F') {
        return value - 'A' + 10;
    }
    return -1;
}

bool decode_hex(
    const char* text,
    std::uint8_t* out,
    std::size_t capacity,
    std::size_t& out_size) {
    out_size = 0;
    if (text == nullptr) {
        return false;
    }
    const std::size_t length = std::strlen(text);
    if (length == 0U || (length % 2U) != 0U || (length / 2U) > capacity) {
        return false;
    }
    for (std::size_t index = 0; index < length; index += 2U) {
        const int high = hex_nibble(text[index]);
        const int low = hex_nibble(text[index + 1U]);
        if (high < 0 || low < 0) {
            out_size = 0;
            return false;
        }
        out[out_size++] = static_cast<std::uint8_t>((high << 4) | low);
    }
    return true;
}

bool contains_prime256v1_oid(const std::uint8_t* data, std::size_t size) {
    if (data == nullptr || size < kPrime256v1Oid.size()) {
        return false;
    }
    for (std::size_t offset = 0; offset + kPrime256v1Oid.size() <= size; ++offset) {
        if (std::memcmp(data + offset, kPrime256v1Oid.data(), kPrime256v1Oid.size()) == 0) {
            return true;
        }
    }
    return false;
}

void write_le32(std::uint8_t* out, std::uint32_t value) {
    out[0] = static_cast<std::uint8_t>(value & 0xFFU);
    out[1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
    out[2] = static_cast<std::uint8_t>((value >> 16U) & 0xFFU);
    out[3] = static_cast<std::uint8_t>((value >> 24U) & 0xFFU);
}

bool sha256(const std::uint8_t* data, std::size_t size, std::uint8_t* out) {
    const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (info == nullptr) {
        return false;
    }
    return mbedtls_md(info, data, size, out) == 0;
}

}  // namespace

bool MaintenanceAuthorizationVerifier::begin(const char* public_key_der_hex) {
    ready_ = false;
    public_key_der_size_ = 0;
    public_key_der_.fill(0);
    public_key_sha256_.fill(0);

    if (!decode_hex(
            public_key_der_hex,
            public_key_der_.data(),
            public_key_der_.size(),
            public_key_der_size_)) {
        return false;
    }
    if (!contains_prime256v1_oid(public_key_der_.data(), public_key_der_size_)) {
        return false;
    }

    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    const int parse_result = mbedtls_pk_parse_public_key(
        &key, public_key_der_.data(), public_key_der_size_);
    if (parse_result != 0) {
        mbedtls_pk_free(&key);
        return false;
    }
    const bool ec_key =
        mbedtls_pk_can_do(&key, MBEDTLS_PK_ECDSA) != 0 ||
        mbedtls_pk_can_do(&key, MBEDTLS_PK_ECKEY) != 0;
    const bool p256_width = mbedtls_pk_get_bitlen(&key) == 256U;
    mbedtls_pk_free(&key);
    if (!ec_key || !p256_width) {
        return false;
    }

    if (!sha256(
            public_key_der_.data(),
            public_key_der_size_,
            public_key_sha256_.data())) {
        public_key_sha256_.fill(0);
        return false;
    }

    ready_ = true;
    return true;
}

bool MaintenanceAuthorizationVerifier::ready() const {
    return ready_;
}

const std::array<std::uint8_t, kAuthorizationFingerprintSize>&
MaintenanceAuthorizationVerifier::public_key_sha256() const {
    return public_key_sha256_;
}

bool MaintenanceAuthorizationVerifier::verify(
    const std::array<std::uint8_t, 6>& device_mac,
    std::uint32_t expected_installed_sequence,
    const std::array<std::uint8_t, kAuthorizationArtifactRootSize>& artifact_root_sha256,
    const std::uint8_t* calibration_record,
    std::size_t calibration_record_size,
    const std::uint8_t* signature_der,
    std::size_t signature_size) const {
    if (!ready_ || calibration_record == nullptr || signature_der == nullptr ||
        calibration_record_size != kCalibrationRecordSize || signature_size == 0U ||
        signature_size > kAuthorizationMaxSignatureSize) {
        return false;
    }

    std::array<std::uint8_t, kAuthorizationPayloadSize> payload{};
    std::size_t offset = 0;
    std::memcpy(payload.data() + offset, kAuthorizationDomain, kAuthorizationDomainSize);
    offset += kAuthorizationDomainSize;
    std::memcpy(payload.data() + offset, device_mac.data(), device_mac.size());
    offset += device_mac.size();
    write_le32(payload.data() + offset, expected_installed_sequence);
    offset += 4U;
    std::memcpy(
        payload.data() + offset,
        artifact_root_sha256.data(),
        artifact_root_sha256.size());
    offset += artifact_root_sha256.size();
    std::memcpy(payload.data() + offset, calibration_record, calibration_record_size);
    offset += calibration_record_size;
    if (offset != payload.size()) {
        return false;
    }

    std::array<std::uint8_t, 32> digest{};
    if (!sha256(payload.data(), payload.size(), digest.data())) {
        return false;
    }

    mbedtls_pk_context key;
    mbedtls_pk_init(&key);
    const int parse_result = mbedtls_pk_parse_public_key(
        &key, public_key_der_.data(), public_key_der_size_);
    if (parse_result != 0) {
        mbedtls_pk_free(&key);
        return false;
    }
    const int verify_result = mbedtls_pk_verify(
        &key,
        MBEDTLS_MD_SHA256,
        digest.data(),
        digest.size(),
        signature_der,
        signature_size);
    mbedtls_pk_free(&key);
    return verify_result == 0;
}

}  // namespace forgesense::maintenance
