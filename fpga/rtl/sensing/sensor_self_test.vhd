library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity sensor_self_test is
    generic (
        TEMP_TIMEOUT_MS : natural := 1000;
        CURRENT_TIMEOUT_MS : natural := 500;
        VIBRATION_TIMEOUT_MS : natural := 500
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        monotonic_ms : in unsigned(31 downto 0);
        temperature_update : in std_logic;
        current_update : in std_logic;
        vibration_update : in std_logic;
        temperature_error : in std_logic;
        current_error : in std_logic;
        vibration_error : in std_logic;
        calibration_valid : in std_logic;
        self_test_pass : out std_logic;
        temperature_alive : out std_logic;
        current_alive : out std_logic;
        vibration_alive : out std_logic
    );
end entity;

architecture rtl of sensor_self_test is
    signal temp_seen, current_seen, vibration_seen : std_logic := '0';
    signal temp_last_ms, current_last_ms, vibration_last_ms : unsigned(31 downto 0) := (others => '0');
    signal temp_fault, current_fault, vibration_fault : std_logic := '0';
    signal temp_alive_i, current_alive_i, vibration_alive_i : std_logic;
begin
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                temp_seen <= '0'; current_seen <= '0'; vibration_seen <= '0';
                temp_last_ms <= (others => '0'); current_last_ms <= (others => '0'); vibration_last_ms <= (others => '0');
                temp_fault <= '0'; current_fault <= '0'; vibration_fault <= '0';
            else
                if temperature_update = '1' then temp_seen <= '1'; temp_last_ms <= monotonic_ms; end if;
                if current_update = '1' then current_seen <= '1'; current_last_ms <= monotonic_ms; end if;
                if vibration_update = '1' then vibration_seen <= '1'; vibration_last_ms <= monotonic_ms; end if;
                if temperature_error = '1' then temp_fault <= '1'; elsif temperature_update = '1' then temp_fault <= '0'; end if;
                if current_error = '1' then current_fault <= '1'; elsif current_update = '1' then current_fault <= '0'; end if;
                if vibration_error = '1' then vibration_fault <= '1'; elsif vibration_update = '1' then vibration_fault <= '0'; end if;
            end if;
        end if;
    end process;

    temp_alive_i <= '1' when temp_seen = '1' and temp_fault = '0' and (monotonic_ms - temp_last_ms) <= to_unsigned(TEMP_TIMEOUT_MS, 32) else '0';
    current_alive_i <= '1' when current_seen = '1' and current_fault = '0' and (monotonic_ms - current_last_ms) <= to_unsigned(CURRENT_TIMEOUT_MS, 32) else '0';
    vibration_alive_i <= '1' when vibration_seen = '1' and vibration_fault = '0' and (monotonic_ms - vibration_last_ms) <= to_unsigned(VIBRATION_TIMEOUT_MS, 32) else '0';

    temperature_alive <= temp_alive_i;
    current_alive <= current_alive_i;
    vibration_alive <= vibration_alive_i;
    self_test_pass <= calibration_valid and temp_alive_i and current_alive_i and vibration_alive_i;
end architecture;
