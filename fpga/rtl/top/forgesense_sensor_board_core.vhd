library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_sensor_board_core is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        UART_BAUD_RATE : positive := 115200;
        SENSOR_SAMPLE_RATE_HZ : positive := 10;
        STATUS_RATE_HZ : positive := 2;
        WATCHDOG_TIMEOUT_MS : positive := 1500;
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
        uart_rx_i : in std_logic;
        uart_tx_o : out std_logic;
        temperature_raw_valid : in std_logic;
        temperature_raw : in signed(23 downto 0);
        current_raw_valid : in std_logic;
        current_raw : in signed(23 downto 0);
        vibration_sample_valid : in std_logic;
        vibration_conditioned_milli_g : in signed(15 downto 0);
        device_identity_ok : in std_logic := '0';
        device_transport_error : in std_logic := '0';
        emergency : in std_logic;
        external_hard_trip : in std_logic := '0';
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        operational_ready : out std_logic;
        uart_framing_error : out std_logic;
        sensor_sample_dropped : out std_logic;
        sensors_valid : out std_logic;
        temperature_numeric_saturated : out std_logic;
        current_numeric_saturated : out std_logic
    );
end entity;

architecture rtl of forgesense_sensor_board_core is
    signal monotonic_ms_i : unsigned(31 downto 0);
    signal temp_update_i, current_update_i, vibration_update_i : std_logic;
    signal temp_i : signed(15 downto 0);
    signal current_i, vibration_i : unsigned(15 downto 0);
    signal temp_valid_i, current_valid_i, vibration_valid_i : std_logic;
    signal sensors_valid_i : std_logic;
begin
    frontend_timebase : entity work.timebase_ms
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ)
        port map (clk => clk, rst => rst, monotonic_ms => monotonic_ms_i);

    frontend : entity work.sensor_frontend
        generic map (
            TEMP_RAW_ZERO => TEMP_RAW_ZERO,
            TEMP_GAIN_NUMERATOR => TEMP_GAIN_NUMERATOR,
            TEMP_GAIN_DENOMINATOR => TEMP_GAIN_DENOMINATOR,
            TEMP_OUTPUT_OFFSET => TEMP_OUTPUT_OFFSET,
            CURRENT_RAW_ZERO => CURRENT_RAW_ZERO,
            CURRENT_GAIN_NUMERATOR => CURRENT_GAIN_NUMERATOR,
            CURRENT_GAIN_DENOMINATOR => CURRENT_GAIN_DENOMINATOR,
            CURRENT_OUTPUT_OFFSET => CURRENT_OUTPUT_OFFSET,
            VIBRATION_WINDOW_SAMPLES => VIBRATION_WINDOW_SAMPLES
        )
        port map (
            clk => clk, rst => rst,
            temperature_raw_valid => temperature_raw_valid,
            temperature_raw => temperature_raw,
            current_raw_valid => current_raw_valid,
            current_raw => current_raw,
            vibration_sample_valid => vibration_sample_valid,
            vibration_conditioned_milli_g => vibration_conditioned_milli_g,
            temperature_update => temp_update_i,
            temperature_deci_c => temp_i,
            current_update => current_update_i,
            current_milli_a => current_i,
            vibration_update => vibration_update_i,
            vibration_milli_g_rms => vibration_i,
            temperature_numeric_saturated => temperature_numeric_saturated,
            current_numeric_saturated => current_numeric_saturated
        );

    supervisor : entity work.sensor_supervisor
        port map (
            clk => clk, rst => rst, monotonic_ms => monotonic_ms_i,
            temperature_update => temp_update_i, temperature_deci_c_in => temp_i,
            vibration_update => vibration_update_i, vibration_milli_g_in => vibration_i,
            current_update => current_update_i, current_milli_a_in => current_i,
            temperature_deci_c => open, vibration_milli_g => open, current_milli_a => open,
            temperature_valid => temp_valid_i, vibration_valid => vibration_valid_i,
            current_valid => current_valid_i, sensors_valid => sensors_valid_i
        );

    board : entity work.forgesense_board_core
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ, UART_BAUD_RATE => UART_BAUD_RATE,
            SENSOR_SAMPLE_RATE_HZ => SENSOR_SAMPLE_RATE_HZ,
            STATUS_RATE_HZ => STATUS_RATE_HZ,
            WATCHDOG_TIMEOUT_MS => WATCHDOG_TIMEOUT_MS
        )
        port map (
            clk => clk, rst => rst, uart_rx_i => uart_rx_i, uart_tx_o => uart_tx_o,
            temperature_deci_c => temp_i, vibration_milli_g => vibration_i,
            current_milli_a => current_i,
            temperature_valid => temp_valid_i, vibration_valid => vibration_valid_i,
            current_valid => current_valid_i,
            device_identity_ok => device_identity_ok,
            device_transport_error => device_transport_error,
            emergency => emergency, external_hard_trip => external_hard_trip,
            recovery_req => recovery_req,
            state_code => state_code, load_enable => load_enable,
            warning_active => warning_active, fault_latched => fault_latched,
            operational_ready => operational_ready,
            uart_framing_error => uart_framing_error,
            sensor_sample_dropped => sensor_sample_dropped
        );

    sensors_valid <= sensors_valid_i;
end architecture;
