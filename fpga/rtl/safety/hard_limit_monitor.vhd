library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity hard_limit_monitor is
    generic (
        TEMP_WARN_DECI_C : natural := 650;
        TEMP_CRIT_DECI_C : natural := 800;
        VIB_WARN_MILLI_G : natural := 600;
        VIB_CRIT_MILLI_G : natural := 1000;
        CURRENT_WARN_MILLI_A : natural := 2500;
        CURRENT_CRIT_MILLI_A : natural := 3200
    );
    port (
        temperature_deci_c : in unsigned(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        sensors_valid : in std_logic;
        hard_warning : out std_logic;
        hard_critical : out std_logic
    );
end entity;

architecture rtl of hard_limit_monitor is
    signal warn_i : std_logic;
    signal crit_i : std_logic;
begin
    crit_i <= '1' when sensors_valid = '0' or
        temperature_deci_c >= to_unsigned(TEMP_CRIT_DECI_C, 16) or
        vibration_milli_g >= to_unsigned(VIB_CRIT_MILLI_G, 16) or
        current_milli_a >= to_unsigned(CURRENT_CRIT_MILLI_A, 16) else '0';
    warn_i <= '1' when crit_i = '0' and (
        temperature_deci_c >= to_unsigned(TEMP_WARN_DECI_C, 16) or
        vibration_milli_g >= to_unsigned(VIB_WARN_MILLI_G, 16) or
        current_milli_a >= to_unsigned(CURRENT_WARN_MILLI_A, 16)) else '0';
    hard_warning <= warn_i;
    hard_critical <= crit_i;
end architecture;
