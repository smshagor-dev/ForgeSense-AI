library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.sensor_device_math_pkg.all;

entity forgesense_reference_sensor_io is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        UART_BAUD_RATE : positive := 115200;
        TMP_I2C_FREQ_HZ : positive := 400000;
        ADXL_SPI_FREQ_HZ : positive := 2000000;
        ADS_SPI_FREQ_HZ : positive := 2000000;
        SENSOR_SAMPLE_RATE_HZ : positive := 10;
        STATUS_RATE_HZ : positive := 2;
        WATCHDOG_TIMEOUT_MS : positive := 1500;
        VIBRATION_WINDOW_SAMPLES : positive := 64
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        uart_rx_i : in std_logic;
        uart_tx_o : out std_logic;
        tmp_scl_in : in std_logic;
        tmp_sda_in : in std_logic;
        tmp_scl_drive_low : out std_logic;
        tmp_sda_drive_low : out std_logic;
        adxl_drdy : in std_logic;
        adxl_miso : in std_logic;
        adxl_cs_n : out std_logic;
        adxl_sclk : out std_logic;
        adxl_mosi : out std_logic;
        ads_drdy_n : in std_logic;
        ads_dout : in std_logic;
        ads_cs_n : out std_logic;
        ads_sclk : out std_logic;
        ads_din : out std_logic;
        emergency : in std_logic;
        analog_hard_trip : in std_logic := '0';
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        operational_ready : out std_logic;
        sensors_valid : out std_logic;
        device_identity_ok : out std_logic;
        device_transport_error : out std_logic
    );
end entity;

architecture rtl of forgesense_reference_sensor_io is
    signal temp_request : std_logic;
    signal tmp_ok, tmp_error, tmp_valid : std_logic;
    signal tmp_deci_c : signed(15 downto 0);
    signal adxl_ok, adxl_error, adxl_valid : std_logic;
    signal adxl_x, adxl_y, adxl_z : signed(15 downto 0);
    signal ads_ok, ads_error, ads_valid : std_logic;
    signal ads_status : std_logic_vector(15 downto 0);
    signal ads_ch0, ads_ch1 : signed(23 downto 0);
    signal inner_phy_error, inner_phy_ok : std_logic;
begin
    temp_scheduler : entity work.sample_scheduler
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SAMPLE_RATE_HZ => SENSOR_SAMPLE_RATE_HZ)
        port map (clk => clk, rst => rst, sample_tick => temp_request);

    temp_device : entity work.tmp117_controller
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, I2C_FREQ_HZ => TMP_I2C_FREQ_HZ)
        port map (
            clk => clk, rst => rst, sample_request => temp_request,
            scl_in => tmp_scl_in, sda_in => tmp_sda_in,
            scl_drive_low => tmp_scl_drive_low, sda_drive_low => tmp_sda_drive_low,
            ready => open, device_ok => tmp_ok, transport_error => tmp_error,
            sample_valid => tmp_valid, temperature_deci_c => tmp_deci_c
        );

    vibration_device : entity work.adxl355_controller
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SPI_FREQ_HZ => ADXL_SPI_FREQ_HZ)
        port map (
            clk => clk, rst => rst, drdy => adxl_drdy, miso => adxl_miso,
            cs_n => adxl_cs_n, sclk => adxl_sclk, mosi => adxl_mosi,
            device_ok => adxl_ok, init_error => adxl_error,
            sample_valid => adxl_valid, x_milli_g => adxl_x,
            y_milli_g => adxl_y, z_milli_g => adxl_z
        );

    current_device : entity work.ads131m02_controller
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SPI_FREQ_HZ => ADS_SPI_FREQ_HZ)
        port map (
            clk => clk, rst => rst, drdy_n => ads_drdy_n, dout => ads_dout,
            cs_n => ads_cs_n, sclk => ads_sclk, din => ads_din,
            device_ok => ads_ok, frame_error => ads_error,
            sample_valid => ads_valid, status_word => ads_status,
            channel0_raw => ads_ch0, channel1_raw => ads_ch1
        );

    platform : entity work.forgesense_phy_board_core
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ,
            UART_BAUD_RATE => UART_BAUD_RATE,
            SENSOR_SAMPLE_RATE_HZ => SENSOR_SAMPLE_RATE_HZ,
            STATUS_RATE_HZ => STATUS_RATE_HZ,
            WATCHDOG_TIMEOUT_MS => WATCHDOG_TIMEOUT_MS,
            TEMP_RAW_ZERO => 0,
            TEMP_GAIN_NUMERATOR => 1,
            TEMP_GAIN_DENOMINATOR => 1,
            TEMP_OUTPUT_OFFSET => 0,
            CURRENT_RAW_ZERO => 0,
            CURRENT_GAIN_NUMERATOR => ADS131M02_CURRENT_MA_NUMERATOR,
            CURRENT_GAIN_DENOMINATOR => ADS131M02_CURRENT_MA_DENOMINATOR,
            CURRENT_OUTPUT_OFFSET => 0,
            VIBRATION_WINDOW_SAMPLES => VIBRATION_WINDOW_SAMPLES,
            VIBRATION_ABS_LIMIT_MILLI_G => 16000
        )
        port map (
            clk => clk, rst => rst, uart_rx_i => uart_rx_i, uart_tx_o => uart_tx_o,
            temperature_sample_valid => tmp_valid,
            temperature_deci_c_sample => tmp_deci_c,
            temperature_sample_error => tmp_error or not tmp_ok,
            current_adc_valid => ads_valid,
            current_adc_signed24 => ads_ch0,
            current_adc_error => ads_error or not ads_ok,
            vibration_sample_valid => adxl_valid,
            vibration_sample_milli_g => adxl_z,
            vibration_sample_error => adxl_error or not adxl_ok,
            emergency => emergency, analog_hard_trip => analog_hard_trip,
            recovery_req => recovery_req,
            state_code => state_code, load_enable => load_enable,
            warning_active => warning_active, fault_latched => fault_latched,
            operational_ready => operational_ready, uart_framing_error => open,
            sensor_sample_dropped => open, sensors_valid => sensors_valid,
            phy_self_test_pass => inner_phy_ok, phy_transport_error => inner_phy_error
        );

    device_identity_ok <= tmp_ok and adxl_ok and ads_ok;
    device_transport_error <= tmp_error or adxl_error or ads_error or inner_phy_error;
end architecture;
