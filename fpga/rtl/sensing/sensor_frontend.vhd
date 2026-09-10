library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity sensor_frontend is
    generic (
        TEMP_RAW_ZERO : integer := 0;
        TEMP_GAIN_NUMERATOR : integer := 1;
        TEMP_GAIN_DENOMINATOR : positive := 1;
        TEMP_OUTPUT_OFFSET : integer := 0;
        CURRENT_RAW_ZERO : integer := 0;
        CURRENT_GAIN_NUMERATOR : integer := 1;
        CURRENT_GAIN_DENOMINATOR : positive := 1;
        CURRENT_OUTPUT_OFFSET : integer := 0;
        VIBRATION_WINDOW_SAMPLES : positive := 64
    );
    port (
        clk : in std_logic;
        rst : in std_logic;

        temperature_raw_valid : in std_logic;
        temperature_raw : in signed(23 downto 0);
        current_raw_valid : in std_logic;
        current_raw : in signed(23 downto 0);
        vibration_sample_valid : in std_logic;
        vibration_conditioned_milli_g : in signed(15 downto 0);

        temperature_update : out std_logic;
        temperature_deci_c : out signed(15 downto 0);
        current_update : out std_logic;
        current_milli_a : out unsigned(15 downto 0);
        vibration_update : out std_logic;
        vibration_milli_g_rms : out unsigned(15 downto 0);
        temperature_numeric_saturated : out std_logic;
        current_numeric_saturated : out std_logic
    );
end entity;

architecture rtl of sensor_frontend is
    signal current_signed_i : signed(15 downto 0);
begin
    temperature_adapter : entity work.linear_sensor_adapter
        generic map (
            RAW_ZERO => TEMP_RAW_ZERO,
            GAIN_NUMERATOR => TEMP_GAIN_NUMERATOR,
            GAIN_DENOMINATOR => TEMP_GAIN_DENOMINATOR,
            OUTPUT_OFFSET => TEMP_OUTPUT_OFFSET
        )
        port map (
            clk => clk,
            rst => rst,
            raw_valid => temperature_raw_valid,
            raw_value => temperature_raw,
            normalized_valid => temperature_update,
            normalized_value => temperature_deci_c,
            numeric_saturated => temperature_numeric_saturated
        );

    current_adapter : entity work.linear_sensor_adapter
        generic map (
            RAW_ZERO => CURRENT_RAW_ZERO,
            GAIN_NUMERATOR => CURRENT_GAIN_NUMERATOR,
            GAIN_DENOMINATOR => CURRENT_GAIN_DENOMINATOR,
            OUTPUT_OFFSET => CURRENT_OUTPUT_OFFSET
        )
        port map (
            clk => clk,
            rst => rst,
            raw_valid => current_raw_valid,
            raw_value => current_raw,
            normalized_valid => current_update,
            normalized_value => current_signed_i,
            numeric_saturated => current_numeric_saturated
        );

    current_milli_a <= unsigned(current_signed_i);

    vibration_feature : entity work.vibration_rms_window
        generic map (
            WINDOW_SAMPLES => VIBRATION_WINDOW_SAMPLES
        )
        port map (
            clk => clk,
            rst => rst,
            sample_valid => vibration_sample_valid,
            conditioned_milli_g => vibration_conditioned_milli_g,
            rms_update => vibration_update,
            rms_milli_g => vibration_milli_g_rms
        );
end architecture;
