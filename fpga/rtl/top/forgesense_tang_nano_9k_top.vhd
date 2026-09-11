library ieee;
use ieee.std_logic_1164.all;

entity forgesense_tang_nano_9k_top is
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

architecture rtl of forgesense_tang_nano_9k_top is
    signal reset_pipe : std_logic_vector(2 downto 0) := (others => '1');
    signal rst_i : std_logic;
    signal tmp_scl_drive_low_i, tmp_sda_drive_low_i : std_logic;
    signal tmp_scl_in_i, tmp_sda_in_i : std_logic;
    signal hard_trip_sync, estop_sync, recovery_sync : std_logic;
    signal state_code_i : std_logic_vector(2 downto 0);
    signal warning_i, fault_i, ready_i, sensors_valid_i : std_logic;
    signal identity_ok_i, transport_error_i : std_logic;
begin
    -- The onboard S2 button is asynchronous to the 27 MHz clock. Reset is
    -- synchronously released after three clean clock edges.
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

    -- Open-drain I2C pins. Pull-ups live on the external sensor board.
    tmp_scl_io <= '0' when tmp_scl_drive_low_i = '1' else 'Z';
    tmp_sda_io <= '0' when tmp_sda_drive_low_i = '1' else 'Z';
    tmp_scl_in_i <= tmp_scl_io;
    tmp_sda_in_i <= tmp_sda_io;

    -- External asynchronous safety/configuration inputs cross into the FPGA
    -- clock domain through two-flop synchronizers. The physical E-stop gate
    -- inhibit remains independent of this clocked observation path.
    hard_trip_sync_inst : entity work.input_sync
        generic map (RESET_VALUE => '0')
        port map (clk => clk_27m_i, rst => rst_i, din => analog_hard_trip_i, dout => hard_trip_sync);

    estop_sync_inst : entity work.input_sync
        generic map (RESET_VALUE => '1')
        port map (clk => clk_27m_i, rst => rst_i, din => estop_sense_i, dout => estop_sync);

    recovery_sync_inst : entity work.input_sync
        generic map (RESET_VALUE => '0')
        port map (clk => clk_27m_i, rst => rst_i, din => recovery_req_i, dout => recovery_sync);

    platform : entity work.forgesense_reference_sensor_io
        generic map (
            CLK_FREQ_HZ => 27000000,
            UART_BAUD_RATE => 115200,
            TMP_I2C_FREQ_HZ => 400000,
            ADXL_SPI_FREQ_HZ => 2000000,
            ADS_SPI_FREQ_HZ => 2000000,
            SENSOR_SAMPLE_RATE_HZ => 10,
            STATUS_RATE_HZ => 2,
            WATCHDOG_TIMEOUT_MS => 1500,
            VIBRATION_WINDOW_SAMPLES => 64
        )
        port map (
            clk => clk_27m_i,
            rst => rst_i,
            uart_rx_i => esp32_uart_rx_i,
            uart_tx_o => esp32_uart_tx_o,
            tmp_scl_in => tmp_scl_in_i,
            tmp_sda_in => tmp_sda_in_i,
            tmp_scl_drive_low => tmp_scl_drive_low_i,
            tmp_sda_drive_low => tmp_sda_drive_low_i,
            adxl_drdy => adxl_drdy_i,
            adxl_miso => adxl_miso_i,
            adxl_cs_n => adxl_cs_n_o,
            adxl_sclk => adxl_sclk_o,
            adxl_mosi => adxl_mosi_o,
            ads_drdy_n => ads_drdy_n_i,
            ads_dout => ads_dout_i,
            ads_cs_n => ads_cs_n_o,
            ads_sclk => ads_sclk_o,
            ads_din => ads_din_o,
            emergency => estop_sync,
            analog_hard_trip => hard_trip_sync,
            recovery_req => recovery_sync,
            state_code => state_code_i,
            load_enable => load_enable_o,
            warning_active => warning_i,
            fault_latched => fault_i,
            operational_ready => ready_i,
            sensors_valid => sensors_valid_i,
            device_identity_ok => identity_ok_i,
            device_transport_error => transport_error_i
        );
end architecture;
