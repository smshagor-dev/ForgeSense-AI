library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_tmp117_controller_behavioral is end entity;

architecture sim of tb_tmp117_controller_behavioral is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal sample_request : std_logic := '0';
    signal master_scl_low, master_sda_low : std_logic;
    signal slave_sda_low : std_logic;
    signal scl_bus, sda_bus : std_logic;
    signal ready, device_ok, transport_error, sample_valid : std_logic;
    signal temperature_deci_c : signed(15 downto 0);
    signal force_nack, force_bad_id : std_logic := '0';
    signal temperature_raw : signed(15 downto 0) := to_signed(16#0C80#, 16);
begin
    clk <= not clk after 5 ns;
    scl_bus <= '0' when master_scl_low = '1' else '1';
    sda_bus <= '0' when master_sda_low = '1' or slave_sda_low = '1' else '1';

    dut : entity work.tmp117_controller
        generic map (CLK_FREQ_HZ => 10000000, I2C_FREQ_HZ => 100000)
        port map (
            clk => clk, rst => rst, sample_request => sample_request,
            scl_in => scl_bus, sda_in => sda_bus,
            scl_drive_low => master_scl_low, sda_drive_low => master_sda_low,
            ready => ready, device_ok => device_ok,
            transport_error => transport_error, sample_valid => sample_valid,
            temperature_deci_c => temperature_deci_c
        );

    sensor : entity work.tmp117_i2c_model
        port map (
            scl => scl_bus, sda => sda_bus, sda_drive_low => slave_sda_low,
            force_nack => force_nack, force_bad_id => force_bad_id,
            temperature_raw => temperature_raw
        );

    process
    begin
        wait for 100 ns;
        rst <= '0';
        wait until device_ok = '1' for 2 ms;
        assert device_ok = '1' report "TMP117 identity probe did not pass" severity error;
        assert ready = '1' report "TMP117 controller did not become ready" severity error;

        wait until rising_edge(clk);
        sample_request <= '1';
        wait until rising_edge(clk);
        sample_request <= '0';
        wait until sample_valid = '1' for 2 ms;
        assert sample_valid = '1' report "TMP117 temperature sample was not published" severity error;
        assert temperature_deci_c = to_signed(250, 16)
            report "TMP117 25 C conversion mismatch" severity error;

        -- Wrong identity must keep the source untrusted.
        rst <= '1'; force_bad_id <= '1';
        wait for 100 ns; rst <= '0';
        wait until transport_error = '1' for 2 ms;
        assert transport_error = '1' report "TMP117 wrong identity was not rejected" severity error;
        assert device_ok = '0' report "TMP117 wrong identity became trusted" severity error;

        -- A bus NACK must surface as a transport fault.
        rst <= '1'; force_bad_id <= '0'; force_nack <= '1';
        wait for 100 ns; rst <= '0';
        wait until transport_error = '1' for 2 ms;
        assert transport_error = '1' report "TMP117 NACK was not surfaced" severity error;
        assert device_ok = '0' report "TMP117 NACK path became trusted" severity error;

        report "tb_tmp117_controller_behavioral PASS" severity note;
        stop; wait;
    end process;
end architecture;
