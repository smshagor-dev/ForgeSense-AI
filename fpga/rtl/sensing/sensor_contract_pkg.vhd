library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package sensor_contract_pkg is
    constant SENSOR_CONTRACT_VERSION : natural := 1;
    constant TEMP_MIN_DECI_C : integer := -400;
    constant TEMP_MAX_DECI_C : integer := 1250;
    constant TEMP_STALE_MS : natural := 1000;
    constant VIB_MIN_MILLI_G : natural := 0;
    constant VIB_MAX_MILLI_G : natural := 16000;
    constant VIB_STALE_MS : natural := 500;
    constant CURRENT_MIN_MILLI_A : natural := 0;
    constant CURRENT_MAX_MILLI_A : natural := 20000;
    constant CURRENT_STALE_MS : natural := 500;
    constant SENSOR_SNAPSHOT_RATE_HZ : natural := 10;
end package;
