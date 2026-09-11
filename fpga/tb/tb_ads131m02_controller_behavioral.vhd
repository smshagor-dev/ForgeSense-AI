library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_ads131m02_controller_behavioral is end entity;

architecture sim of tb_ads131m02_controller_behavioral is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal drdy_n : std_logic := '1';
    signal cs_n, sclk, din, dout : std_logic;
    signal device_ok, frame_error, sample_valid : std_logic;
    signal status_word : std_logic_vector(15 downto 0);
    signal ch0, ch1 : signed(23 downto 0);
    signal force_bad_id, force_bad_crc : std_logic := '0';
    constant CH0_VALUE : signed(23 downto 0) := to_signed(16#100000#, 24);
    constant CH1_VALUE : signed(23 downto 0) := to_signed(-16#080000#, 24);
begin
    clk <= not clk after 5 ns;

    dut : entity work.ads131m02_controller
        generic map (CLK_FREQ_HZ => 10000000, SPI_FREQ_HZ => 1000000)
        port map (
            clk => clk, rst => rst, drdy_n => drdy_n, dout => dout,
            cs_n => cs_n, sclk => sclk, din => din,
            device_ok => device_ok, frame_error => frame_error,
            sample_valid => sample_valid, status_word => status_word,
            channel0_raw => ch0, channel1_raw => ch1
        );

    sensor : entity work.ads131m02_spi_model
        port map (
            cs_n => cs_n, sclk => sclk, din => din, dout => dout,
            force_bad_id => force_bad_id, force_bad_crc => force_bad_crc,
            channel0_raw => CH0_VALUE, channel1_raw => CH1_VALUE
        );

    process
        procedure pulse_drdy is
        begin
            drdy_n <= '0'; wait for 200 ns;
            drdy_n <= '1';
        end procedure;
    begin
        wait for 100 ns; rst <= '0';

        -- RREG ID command/response, CLOCK write, CLOCK read command/response.
        for i in 0 to 4 loop
            pulse_drdy;
            wait for 130 us;
        end loop;
        assert device_ok = '1' report "ADS131M02 startup verification did not pass" severity error;

        pulse_drdy;
        wait until sample_valid = '1' for 200 us;
        assert sample_valid = '1' report "ADS131M02 sample frame was not published" severity error;
        assert status_word = x"05A0" report "ADS131M02 status word mismatch" severity error;
        assert ch0 = CH0_VALUE report "ADS131M02 channel 0 mismatch" severity error;
        assert ch1 = CH1_VALUE report "ADS131M02 channel 1 mismatch" severity error;
        wait for 10 us;

        -- A corrupted mandatory output CRC must suppress publication.
        force_bad_crc <= '1';
        pulse_drdy;
        wait until frame_error = '1' for 200 us;
        assert frame_error = '1' report "ADS131M02 CRC corruption was not rejected" severity error;
        wait for 10 us;

        -- Reset and prove a wrong identity cannot become trusted.
        rst <= '1'; force_bad_crc <= '0'; force_bad_id <= '1';
        wait for 100 ns; rst <= '0';
        pulse_drdy; wait for 130 us;
        pulse_drdy;
        wait until frame_error = '1' for 200 us;
        assert frame_error = '1' report "ADS131M02 wrong identity was not surfaced" severity error;
        assert device_ok = '0' report "ADS131M02 wrong identity became trusted" severity error;

        report "tb_ads131m02_controller_behavioral PASS" severity note;
        stop; wait;
    end process;
end architecture;
