library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.sensor_contract_pkg.all;

entity sensor_supervisor is
    port (
        clk : in std_logic;
        rst : in std_logic;
        monotonic_ms : in unsigned(31 downto 0);
        temperature_update : in std_logic;
        temperature_deci_c_in : in signed(15 downto 0);
        vibration_update : in std_logic;
        vibration_milli_g_in : in unsigned(15 downto 0);
        current_update : in std_logic;
        current_milli_a_in : in unsigned(15 downto 0);
        temperature_deci_c : out signed(15 downto 0);
        vibration_milli_g : out unsigned(15 downto 0);
        current_milli_a : out unsigned(15 downto 0);
        temperature_valid : out std_logic;
        vibration_valid : out std_logic;
        current_valid : out std_logic;
        sensors_valid : out std_logic
    );
end entity;

architecture rtl of sensor_supervisor is
    signal temp_value : signed(15 downto 0) := (others => '0');
    signal vib_value : unsigned(15 downto 0) := (others => '0');
    signal current_value : unsigned(15 downto 0) := (others => '0');
    signal temp_last_ms, vib_last_ms, current_last_ms : unsigned(31 downto 0) := (others => '0');
    signal temp_seen, vib_seen, current_seen : std_logic := '0';
    signal temp_plausible, vib_plausible, current_plausible : std_logic := '0';
    signal temp_valid_i, vib_valid_i, current_valid_i : std_logic;
begin
    process(clk)
        variable temp_integer : integer;
    begin
        if rising_edge(clk) then
            if rst = '1' then
                temp_value <= (others => '0');
                vib_value <= (others => '0');
                current_value <= (others => '0');
                temp_last_ms <= (others => '0');
                vib_last_ms <= (others => '0');
                current_last_ms <= (others => '0');
                temp_seen <= '0';
                vib_seen <= '0';
                current_seen <= '0';
                temp_plausible <= '0';
                vib_plausible <= '0';
                current_plausible <= '0';
            else
                if temperature_update = '1' then
                    temp_value <= temperature_deci_c_in;
                    temp_last_ms <= monotonic_ms;
                    temp_seen <= '1';
                    temp_integer := to_integer(temperature_deci_c_in);
                    if temp_integer >= TEMP_MIN_DECI_C and temp_integer <= TEMP_MAX_DECI_C then
                        temp_plausible <= '1';
                    else
                        temp_plausible <= '0';
                    end if;
                end if;
                if vibration_update = '1' then
                    vib_value <= vibration_milli_g_in;
                    vib_last_ms <= monotonic_ms;
                    vib_seen <= '1';
                    if to_integer(vibration_milli_g_in) >= VIB_MIN_MILLI_G and to_integer(vibration_milli_g_in) <= VIB_MAX_MILLI_G then
                        vib_plausible <= '1';
                    else
                        vib_plausible <= '0';
                    end if;
                end if;
                if current_update = '1' then
                    current_value <= current_milli_a_in;
                    current_last_ms <= monotonic_ms;
                    current_seen <= '1';
                    if to_integer(current_milli_a_in) >= CURRENT_MIN_MILLI_A and to_integer(current_milli_a_in) <= CURRENT_MAX_MILLI_A then
                        current_plausible <= '1';
                    else
                        current_plausible <= '0';
                    end if;
                end if;
            end if;
        end if;
    end process;

    temp_valid_i <= '1' when temp_seen = '1' and temp_plausible = '1' and (monotonic_ms - temp_last_ms) <= to_unsigned(TEMP_STALE_MS, 32) else '0';
    vib_valid_i <= '1' when vib_seen = '1' and vib_plausible = '1' and (monotonic_ms - vib_last_ms) <= to_unsigned(VIB_STALE_MS, 32) else '0';
    current_valid_i <= '1' when current_seen = '1' and current_plausible = '1' and (monotonic_ms - current_last_ms) <= to_unsigned(CURRENT_STALE_MS, 32) else '0';

    temperature_deci_c <= temp_value;
    vibration_milli_g <= vib_value;
    current_milli_a <= current_value;
    temperature_valid <= temp_valid_i;
    vibration_valid <= vib_valid_i;
    current_valid <= current_valid_i;
    sensors_valid <= temp_valid_i and vib_valid_i and current_valid_i;
end architecture;
