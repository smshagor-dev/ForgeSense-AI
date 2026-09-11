library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_adxl355_controller_behavioral is end entity;

architecture sim of tb_adxl355_controller_behavioral is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal drdy : std_logic := '0';
    signal cs_n, sclk, mosi, miso : std_logic;
    signal device_ok, init_error, sample_valid : std_logic;
    signal x_mg, y_mg, z_mg : signed(15 downto 0);
    signal force_bad_id, force_bad_config : std_logic := '0';
begin
    clk <= not clk after 5 ns;

    dut : entity work.adxl355_controller
        generic map (CLK_FREQ_HZ => 10000000, SPI_FREQ_HZ => 1000000)
        port map (
            clk => clk, rst => rst, drdy => drdy, miso => miso,
            cs_n => cs_n, sclk => sclk, mosi => mosi,
            device_ok => device_ok, init_error => init_error,
            sample_valid => sample_valid, x_milli_g => x_mg,
            y_milli_g => y_mg, z_milli_g => z_mg
        );

    sensor : entity work.adxl355_spi_model
        port map (
            cs_n => cs_n, sclk => sclk, mosi => mosi, miso => miso,
            force_bad_id => force_bad_id, force_bad_config => force_bad_config,
            x_raw20 => to_signed(10000, 20),
            y_raw20 => to_signed(-10000, 20),
            z_raw20 => to_signed(20000, 20)
        );

    process
    begin
        wait for 100 ns; rst <= '0';
        wait until device_ok = '1' for 3 ms;
        assert device_ok = '1' report "ADXL355 identity/configuration did not pass" severity error;
        assert init_error = '0' report "ADXL355 unexpectedly reported initialization fault" severity error;

        wait until rising_edge(clk); drdy <= '1';
        wait until rising_edge(clk); drdy <= '0';
        wait until sample_valid = '1' for 1 ms;
        assert sample_valid = '1' report "ADXL355 burst sample was not published" severity error;
        assert x_mg = to_signed(156, 16) report "ADXL355 X conversion mismatch" severity error;
        assert y_mg = to_signed(-156, 16) report "ADXL355 Y conversion mismatch" severity error;
        assert z_mg = to_signed(312, 16) report "ADXL355 Z conversion mismatch" severity error;

        rst <= '1'; force_bad_id <= '1';
        wait for 100 ns; rst <= '0';
        wait until init_error = '1' for 2 ms;
        assert init_error = '1' report "ADXL355 wrong identity was not rejected" severity error;
        assert device_ok = '0' report "ADXL355 wrong identity became trusted" severity error;

        rst <= '1'; force_bad_id <= '0'; force_bad_config <= '1';
        wait for 100 ns; rst <= '0';
        wait until init_error = '1' for 3 ms;
        assert init_error = '1' report "ADXL355 configuration readback corruption was not rejected" severity error;
        assert device_ok = '0' report "ADXL355 bad configuration became trusted" severity error;

        report "tb_adxl355_controller_behavioral PASS" severity note;
        stop; wait;
    end process;
end architecture;
