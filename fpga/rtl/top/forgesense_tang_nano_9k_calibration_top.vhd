library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_tang_nano_9k_calibration_top is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        UART_BAUD_RATE : positive := 115200;
        DIAGNOSTIC_RATE_HZ : positive := 20
    );
    port (
        clk_27m_i : in std_logic;
        reset_n_i : in std_logic;
        esp32_uart_rx_i : in std_logic;
        esp32_uart_tx_o : out std_logic;
        tmp_scl_io : inout std_logic;
        tmp_sda_io : inout std_logic;
        adxl_drdy_i : in std_logic;
        adxl_miso_i : in std_logic;
        adxl_cs_n_o : out std_logic;
        adxl_sclk_o : out std_logic;
        adxl_mosi_o : out std_logic;
        ads_drdy_n_i : in std_logic;
        ads_dout_i : in std_logic;
        ads_cs_n_o : out std_logic;
        ads_sclk_o : out std_logic;
        ads_din_o : out std_logic;
        analog_hard_trip_i : in std_logic;
        estop_sense_i : in std_logic;
        recovery_req_i : in std_logic;
        load_enable_o : out std_logic
    );
end entity;

architecture rtl of forgesense_tang_nano_9k_calibration_top is
    signal reset_pipe : std_logic_vector(2 downto 0) := (others => '1');
    signal rst_i : std_logic;
    signal monotonic_ms_i : unsigned(31 downto 0);
    signal temp_request_i, diagnostic_tick_i : std_logic;
    signal tmp_scl_drive_low_i, tmp_sda_drive_low_i : std_logic;
    signal tmp_scl_in_i, tmp_sda_in_i : std_logic;
    signal tmp_ok_i, tmp_error_i, tmp_valid_i : std_logic;
    signal tmp_deci_c_i : signed(15 downto 0);
    signal adxl_ok_i, adxl_error_i, adxl_valid_i : std_logic;
    signal adxl_x_i, adxl_y_i, adxl_z_i : signed(15 downto 0);
    signal ads_ok_i, ads_error_i, ads_valid_i : std_logic;
    signal ads_status_i : std_logic_vector(15 downto 0);
    signal ads_ch0_i, ads_ch1_i : signed(23 downto 0);
    signal tmp_seen_i, adxl_seen_i, ads_seen_i : std_logic := '0';
    signal tmp_error_latched_i, adxl_error_latched_i, ads_error_latched_i : std_logic := '0';
    signal diagnostic_flags_i : unsigned(15 downto 0) := (others => '0');
    signal tx_ready_i, tx_valid_i, diagnostic_dropped_i : std_logic;
    signal tx_byte_i : std_logic_vector(7 downto 0);
begin
    process(clk_27m_i)
    begin
        if rising_edge(clk_27m_i) then
            if reset_n_i = '0' then
                reset_pipe <= (others => '1');
            else
                reset_pipe <= reset_pipe(1 downto 0) & '0';
            end if;
        end if;
    end process;
    rst_i <= reset_pipe(2);

    tmp_scl_io <= '0' when tmp_scl_drive_low_i = '1' else 'Z';
    tmp_sda_io <= '0' when tmp_sda_drive_low_i = '1' else 'Z';
    tmp_scl_in_i <= tmp_scl_io;
    tmp_sda_in_i <= tmp_sda_io;

    clock_ms : entity work.timebase_ms
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ)
        port map (clk => clk_27m_i, rst => rst_i, monotonic_ms => monotonic_ms_i);

    temp_scheduler : entity work.sample_scheduler
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SAMPLE_RATE_HZ => 10)
        port map (clk => clk_27m_i, rst => rst_i, sample_tick => temp_request_i);

    diagnostic_scheduler : entity work.sample_scheduler
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SAMPLE_RATE_HZ => DIAGNOSTIC_RATE_HZ)
        port map (clk => clk_27m_i, rst => rst_i, sample_tick => diagnostic_tick_i);

    temp_device : entity work.tmp117_controller
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, I2C_FREQ_HZ => 400000)
        port map (
            clk => clk_27m_i, rst => rst_i, sample_request => temp_request_i,
            scl_in => tmp_scl_in_i, sda_in => tmp_sda_in_i,
            scl_drive_low => tmp_scl_drive_low_i, sda_drive_low => tmp_sda_drive_low_i,
            ready => open, device_ok => tmp_ok_i, transport_error => tmp_error_i,
            sample_valid => tmp_valid_i, temperature_deci_c => tmp_deci_c_i
        );

    vibration_device : entity work.adxl355_controller
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SPI_FREQ_HZ => 2000000)
        port map (
            clk => clk_27m_i, rst => rst_i, drdy => adxl_drdy_i, miso => adxl_miso_i,
            cs_n => adxl_cs_n_o, sclk => adxl_sclk_o, mosi => adxl_mosi_o,
            device_ok => adxl_ok_i, init_error => adxl_error_i,
            sample_valid => adxl_valid_i, x_milli_g => adxl_x_i,
            y_milli_g => adxl_y_i, z_milli_g => adxl_z_i
        );

    current_device : entity work.ads131m02_controller
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SPI_FREQ_HZ => 2000000)
        port map (
            clk => clk_27m_i, rst => rst_i, drdy_n => ads_drdy_n_i, dout => ads_dout_i,
            cs_n => ads_cs_n_o, sclk => ads_sclk_o, din => ads_din_o,
            device_ok => ads_ok_i, frame_error => ads_error_i,
            sample_valid => ads_valid_i, status_word => ads_status_i,
            channel0_raw => ads_ch0_i, channel1_raw => ads_ch1_i
        );

    process(clk_27m_i)
    begin
        if rising_edge(clk_27m_i) then
            if rst_i = '1' then
                tmp_seen_i <= '0';
                adxl_seen_i <= '0';
                ads_seen_i <= '0';
                tmp_error_latched_i <= '0';
                adxl_error_latched_i <= '0';
                ads_error_latched_i <= '0';
            else
                if tmp_valid_i = '1' then tmp_seen_i <= '1'; end if;
                if adxl_valid_i = '1' then adxl_seen_i <= '1'; end if;
                if ads_valid_i = '1' then ads_seen_i <= '1'; end if;
                if tmp_error_i = '1' then tmp_error_latched_i <= '1'; end if;
                if adxl_error_i = '1' then adxl_error_latched_i <= '1'; end if;
                if ads_error_i = '1' then ads_error_latched_i <= '1'; end if;
            end if;
        end if;
    end process;

    diagnostic_flags_i <=
        (0 => tmp_seen_i,
         1 => adxl_seen_i,
         2 => ads_seen_i,
         3 => tmp_ok_i,
         4 => adxl_ok_i,
         5 => ads_ok_i,
         6 => tmp_error_latched_i,
         7 => adxl_error_latched_i,
         8 => ads_error_latched_i,
         others => '0');

    diagnostic_tx : entity work.calibration_diag_tx
        port map (
            clk => clk_27m_i,
            rst => rst_i,
            sample_trigger => diagnostic_tick_i,
            timestamp_ms => monotonic_ms_i,
            ads_ch0_raw => ads_ch0_i,
            ads_ch1_raw => ads_ch1_i,
            tmp_deci_c => tmp_deci_c_i,
            adxl_x_milli_g => adxl_x_i,
            adxl_y_milli_g => adxl_y_i,
            adxl_z_milli_g => adxl_z_i,
            diagnostic_flags => diagnostic_flags_i,
            tx_ready => tx_ready_i,
            tx_valid => tx_valid_i,
            tx_byte => tx_byte_i,
            sample_dropped => diagnostic_dropped_i
        );

    serial_tx : entity work.uart_tx
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, BAUD_RATE => UART_BAUD_RATE)
        port map (
            clk => clk_27m_i, rst => rst_i,
            data_valid => tx_valid_i, data_byte => tx_byte_i,
            ready => tx_ready_i, tx_serial => esp32_uart_tx_o
        );

    -- Calibration image is observation-only. It never authorizes the external
    -- power stage, regardless of UART input, E-stop, recovery, or trip state.
    load_enable_o <= '0';

    -- PC-to-FPGA UART and safety inputs remain physically mapped for harness
    -- compatibility but create no command or actuator path in this image.
end architecture;
