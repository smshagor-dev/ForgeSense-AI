library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_selected_sensor_cluster_behavioral is end entity;

architecture sim of tb_selected_sensor_cluster_behavioral is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';

    signal tmp_request : std_logic := '0';
    signal tmp_master_scl_low, tmp_master_sda_low, tmp_slave_sda_low : std_logic;
    signal tmp_scl_bus, tmp_sda_bus : std_logic;
    signal tmp_ok, tmp_error, tmp_valid : std_logic;
    signal tmp_value : signed(15 downto 0);

    signal adxl_drdy : std_logic := '0';
    signal adxl_cs_n, adxl_sclk, adxl_mosi, adxl_miso : std_logic;
    signal adxl_ok, adxl_error, adxl_valid : std_logic;
    signal adxl_x, adxl_y, adxl_z : signed(15 downto 0);

    signal ads_drdy_n : std_logic := '1';
    signal ads_cs_n, ads_sclk, ads_din, ads_dout : std_logic;
    signal ads_ok, ads_error, ads_valid : std_logic;
    signal ads_status : std_logic_vector(15 downto 0);
    signal ads_ch0, ads_ch1 : signed(23 downto 0);

    constant ADS_CH0 : signed(23 downto 0) := to_signed(16#0C0000#, 24);
    constant ADS_CH1 : signed(23 downto 0) := to_signed(16#010000#, 24);
begin
    clk <= not clk after 5 ns;
    tmp_scl_bus <= '0' when tmp_master_scl_low = '1' else '1';
    tmp_sda_bus <= '0' when tmp_master_sda_low = '1' or tmp_slave_sda_low = '1' else '1';

    tmp_dut : entity work.tmp117_controller
        generic map (CLK_FREQ_HZ => 10000000, I2C_FREQ_HZ => 100000)
        port map (
            clk => clk, rst => rst, sample_request => tmp_request,
            scl_in => tmp_scl_bus, sda_in => tmp_sda_bus,
            scl_drive_low => tmp_master_scl_low, sda_drive_low => tmp_master_sda_low,
            ready => open, device_ok => tmp_ok, transport_error => tmp_error,
            sample_valid => tmp_valid, temperature_deci_c => tmp_value
        );

    tmp_sensor : entity work.tmp117_i2c_model
        port map (
            scl => tmp_scl_bus, sda => tmp_sda_bus, sda_drive_low => tmp_slave_sda_low,
            force_nack => '0', force_bad_id => '0',
            temperature_raw => to_signed(16#0C80#, 16)
        );

    adxl_dut : entity work.adxl355_controller
        generic map (CLK_FREQ_HZ => 10000000, SPI_FREQ_HZ => 1000000)
        port map (
            clk => clk, rst => rst, drdy => adxl_drdy, miso => adxl_miso,
            cs_n => adxl_cs_n, sclk => adxl_sclk, mosi => adxl_mosi,
            device_ok => adxl_ok, init_error => adxl_error,
            sample_valid => adxl_valid, x_milli_g => adxl_x,
            y_milli_g => adxl_y, z_milli_g => adxl_z
        );

    adxl_sensor : entity work.adxl355_spi_model
        port map (
            cs_n => adxl_cs_n, sclk => adxl_sclk, mosi => adxl_mosi, miso => adxl_miso,
            force_bad_id => '0', force_bad_config => '0',
            x_raw20 => to_signed(10000, 20),
            y_raw20 => to_signed(-10000, 20), z_raw20 => to_signed(20000, 20)
        );

    ads_dut : entity work.ads131m02_controller
        generic map (CLK_FREQ_HZ => 10000000, SPI_FREQ_HZ => 1000000)
        port map (
            clk => clk, rst => rst, drdy_n => ads_drdy_n, dout => ads_dout,
            cs_n => ads_cs_n, sclk => ads_sclk, din => ads_din,
            device_ok => ads_ok, frame_error => ads_error,
            sample_valid => ads_valid, status_word => ads_status,
            channel0_raw => ads_ch0, channel1_raw => ads_ch1
        );

    ads_sensor : entity work.ads131m02_spi_model
        port map (
            cs_n => ads_cs_n, sclk => ads_sclk, din => ads_din, dout => ads_dout,
            force_bad_id => '0', force_bad_crc => '0',
            channel0_raw => ADS_CH0, channel1_raw => ADS_CH1
        );

    process
        procedure pulse_ads_drdy is
        begin
            ads_drdy_n <= '0'; wait for 200 ns; ads_drdy_n <= '1';
        end procedure;
    begin
        wait for 100 ns; rst <= '0';

        wait until tmp_ok = '1' for 2 ms;
        assert tmp_ok = '1' and tmp_error = '0'
            report "TMP117 did not become healthy in cluster verification" severity error;

        wait until adxl_ok = '1' for 3 ms;
        assert adxl_ok = '1' and adxl_error = '0'
            report "ADXL355 did not become healthy in cluster verification" severity error;

        for i in 0 to 4 loop
            pulse_ads_drdy;
            wait for 130 us;
        end loop;
        assert ads_ok = '1' and ads_error = '0'
            report "ADS131M02 did not become healthy in cluster verification" severity error;

        wait until rising_edge(clk); tmp_request <= '1';
        wait until rising_edge(clk); tmp_request <= '0';
        wait until tmp_valid = '1' for 2 ms;
        assert tmp_valid = '1' and tmp_value = to_signed(250, 16)
            report "TMP117 cluster sample mismatch" severity error;

        wait until rising_edge(clk); adxl_drdy <= '1';
        wait until rising_edge(clk); adxl_drdy <= '0';
        wait until adxl_valid = '1' for 1 ms;
        assert adxl_valid = '1' and adxl_z = to_signed(312, 16)
            report "ADXL355 cluster sample mismatch" severity error;

        pulse_ads_drdy;
        wait until ads_valid = '1' for 200 us;
        assert ads_valid = '1' report "ADS131M02 cluster sample missing" severity error;
        assert ads_status = x"05A0" report "ADS131M02 cluster status mismatch" severity error;
        assert ads_ch0 = ADS_CH0 and ads_ch1 = ADS_CH1
            report "ADS131M02 cluster channel mismatch" severity error;

        assert tmp_ok = '1' and adxl_ok = '1' and ads_ok = '1'
            report "selected sensor cluster lost trusted identity state" severity error;

        report "tb_selected_sensor_cluster_behavioral PASS" severity note;
        stop; wait;
    end process;
end architecture;
