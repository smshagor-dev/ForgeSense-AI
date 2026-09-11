library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_phy_board_core is
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
        VIBRATION_WINDOW_SAMPLES : positive := 64;
        VIBRATION_ABS_LIMIT_MILLI_G : positive := 16000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        uart_rx_i : in std_logic;
        uart_tx_o : out std_logic;
        temperature_sample_valid : in std_logic;
        temperature_deci_c_sample : in signed(15 downto 0);
        temperature_sample_error : in std_logic;
        current_adc_valid : in std_logic;
        current_adc_signed24 : in signed(23 downto 0);
        current_adc_error : in std_logic;
        vibration_sample_valid : in std_logic;
        vibration_sample_milli_g : in signed(15 downto 0);
        vibration_sample_error : in std_logic;
        device_identity_ok : in std_logic := '0';
        device_transport_error : in std_logic := '0';
        emergency : in std_logic;
        analog_hard_trip : in std_logic := '0';
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        operational_ready : out std_logic;
        uart_framing_error : out std_logic;
        sensor_sample_dropped : out std_logic;
        sensors_valid : out std_logic;
        phy_self_test_pass : out std_logic;
        phy_transport_error : out std_logic
    );
end entity;

architecture rtl of forgesense_phy_board_core is
    signal monotonic_ms_i : unsigned(31 downto 0);
    signal temp_norm_valid : std_logic;
    signal temp_norm : signed(15 downto 0);
    signal temp_error_i : std_logic;
    signal current_raw_valid_i : std_logic;
    signal current_raw_i : signed(23 downto 0);
    signal current_error_i : std_logic;
    signal vibration_conditioned_valid_i : std_logic;
    signal vibration_conditioned_i : signed(15 downto 0);
    signal vibration_range_error_i : std_logic;
    signal vibration_transport_error_i : std_logic;
    signal temp_raw24_i : signed(23 downto 0);
    signal self_test_i : std_logic;
    signal combined_transport_error_i : std_logic;
begin
    phy_timebase : entity work.timebase_ms
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ)
        port map (clk => clk, rst => rst, monotonic_ms => monotonic_ms_i);

    temperature_phy : entity work.digital_temperature_adapter
        port map (
            clk => clk, rst => rst, sample_valid => temperature_sample_valid,
            temperature_deci_c_in => temperature_deci_c_sample,
            sample_error => temperature_sample_error,
            normalized_valid => temp_norm_valid,
            normalized_temperature_deci_c => temp_norm,
            diagnostic_error => temp_error_i
        );

    temp_raw24_i <= resize(temp_norm, 24);

    current_phy : entity work.generic_adc_sample_adapter
        port map (
            clk => clk, rst => rst, sample_valid => current_adc_valid,
            sample_signed24 => current_adc_signed24, sample_error => current_adc_error,
            raw_valid => current_raw_valid_i, raw_value => current_raw_i,
            diagnostic_error => current_error_i
        );

    vibration_phy : entity work.accelerometer_conditioner
        generic map (ABS_LIMIT_MILLI_G => VIBRATION_ABS_LIMIT_MILLI_G)
        port map (
            clk => clk, rst => rst, sample_valid => vibration_sample_valid,
            sample_milli_g => vibration_sample_milli_g,
            sample_error => vibration_sample_error,
            conditioned_valid => vibration_conditioned_valid_i,
            conditioned_milli_g => vibration_conditioned_i,
            range_error => vibration_range_error_i,
            transport_error => vibration_transport_error_i
        );

    phy_self_test : entity work.sensor_self_test
        port map (
            clk => clk, rst => rst, monotonic_ms => monotonic_ms_i,
            temperature_update => temp_norm_valid,
            current_update => current_raw_valid_i,
            vibration_update => vibration_conditioned_valid_i,
            temperature_error => temp_error_i,
            current_error => current_error_i,
            vibration_error => vibration_range_error_i or vibration_transport_error_i,
            calibration_valid => '1', self_test_pass => self_test_i,
            temperature_alive => open, current_alive => open, vibration_alive => open
        );

    combined_transport_error_i <= device_transport_error or temp_error_i or current_error_i or
                                  vibration_range_error_i or vibration_transport_error_i;

    sensor_board : entity work.forgesense_sensor_board_core
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ, UART_BAUD_RATE => UART_BAUD_RATE,
            SENSOR_SAMPLE_RATE_HZ => SENSOR_SAMPLE_RATE_HZ,
            STATUS_RATE_HZ => STATUS_RATE_HZ,
            WATCHDOG_TIMEOUT_MS => WATCHDOG_TIMEOUT_MS,
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
            clk => clk, rst => rst, uart_rx_i => uart_rx_i, uart_tx_o => uart_tx_o,
            temperature_raw_valid => temp_norm_valid, temperature_raw => temp_raw24_i,
            current_raw_valid => current_raw_valid_i, current_raw => current_raw_i,
            vibration_sample_valid => vibration_conditioned_valid_i,
            vibration_conditioned_milli_g => vibration_conditioned_i,
            device_identity_ok => device_identity_ok,
            device_transport_error => combined_transport_error_i,
            emergency => emergency, external_hard_trip => analog_hard_trip,
            recovery_req => recovery_req,
            state_code => state_code, load_enable => load_enable,
            warning_active => warning_active, fault_latched => fault_latched,
            operational_ready => operational_ready,
            uart_framing_error => uart_framing_error,
            sensor_sample_dropped => sensor_sample_dropped,
            sensors_valid => sensors_valid,
            temperature_numeric_saturated => open,
            current_numeric_saturated => open
        );

    phy_self_test_pass <= self_test_i;
    phy_transport_error <= combined_transport_error_i;
end architecture;
