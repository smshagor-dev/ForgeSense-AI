library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_sensor_phy_reference is end entity;

architecture sim of tb_sensor_phy_reference is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal valid : std_logic := '0';
    signal raw : signed(23 downto 0) := (others => '0');
    signal err : std_logic := '0';
    signal raw_valid : std_logic;
    signal raw_out : signed(23 downto 0);
    signal diag : std_logic;

    signal av : std_logic := '0';
    signal accel : signed(15 downto 0) := (others => '0');
    signal aout_valid : std_logic;
    signal aout : signed(15 downto 0);
    signal range_error, transport_error : std_logic;
begin
    clk <= not clk after 5 ns;

    adc : entity work.generic_adc_sample_adapter
        port map (clk, rst, valid, raw, err, raw_valid, raw_out, diag);

    conditioner : entity work.accelerometer_conditioner
        generic map (ABS_LIMIT_MILLI_G => 16000)
        port map (clk, rst, av, accel, err, aout_valid, aout, range_error, transport_error);

    process
    begin
        wait for 20 ns; rst <= '0';
        raw <= to_signed(12345, 24); valid <= '1';
        wait for 10 ns; valid <= '0'; wait for 1 ns;
        assert raw_valid = '1' report "ADC sample not accepted" severity error;
        assert raw_out = to_signed(12345, 24) severity error;

        wait for 9 ns; err <= '1'; valid <= '1';
        wait for 10 ns; valid <= '0'; err <= '0'; wait for 1 ns;
        assert diag = '1' report "ADC error not surfaced" severity error;

        wait for 9 ns; accel <= to_signed(3000, 16); av <= '1';
        wait for 10 ns; av <= '0'; wait for 1 ns;
        assert aout_valid = '1' and aout = to_signed(3000,16) severity error;

        wait for 9 ns; accel <= to_signed(20000, 16); av <= '1';
        wait for 10 ns; av <= '0'; wait for 1 ns;
        assert range_error = '1' report "accelerometer range error missing" severity error;

        report "tb_sensor_phy_reference PASS" severity note;
        wait;
    end process;
end architecture;
