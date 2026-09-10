library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_sensor_supervisor is
end entity;

architecture sim of tb_sensor_supervisor is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal ms : unsigned(31 downto 0) := (others => '0');
    signal tu, vu, cu : std_logic := '0';
    signal tin : signed(15 downto 0) := (others => '0');
    signal vin, cin : unsigned(15 downto 0) := (others => '0');
    signal tout : signed(15 downto 0);
    signal vout, cout : unsigned(15 downto 0);
    signal tv, vv, cv, allv : std_logic;
begin
    clk <= not clk after 5 ns;
    dut : entity work.sensor_supervisor
        port map (clk, rst, ms, tu, tin, vu, vin, cu, cin, tout, vout, cout, tv, vv, cv, allv);

    stimulus : process
    begin
        wait for 20 ns;
        rst <= '0';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert allv = '0' report "unseen sensors must be invalid" severity failure;

        tin <= to_signed(420, 16);
        vin <= to_unsigned(250, 16);
        cin <= to_unsigned(1200, 16);
        tu <= '1'; vu <= '1'; cu <= '1';
        wait until rising_edge(clk);
        tu <= '0'; vu <= '0'; cu <= '0';
        wait for 1 ns;
        assert allv = '1' report "fresh plausible samples must be valid" severity failure;

        ms <= to_unsigned(501, 32);
        wait until rising_edge(clk);
        wait for 1 ns;
        assert vv = '0' and cv = '0' and allv = '0' report "stale fast channels must invalidate" severity failure;

        ms <= to_unsigned(600, 32);
        vin <= to_unsigned(17000, 16); vu <= '1';
        cin <= to_unsigned(1300, 16); cu <= '1';
        wait until rising_edge(clk);
        vu <= '0'; cu <= '0';
        wait for 1 ns;
        assert vv = '0' report "implausible vibration must be rejected" severity failure;

        ms <= to_unsigned(601, 32);
        vin <= to_unsigned(300, 16); vu <= '1';
        wait until rising_edge(clk);
        vu <= '0';
        wait for 1 ns;
        assert vv = '1' report "new plausible vibration must recover channel" severity failure;

        ms <= to_unsigned(1001, 32);
        wait until rising_edge(clk);
        wait for 1 ns;
        assert tv = '0' report "temperature freshness timeout must invalidate" severity failure;
        report "tb_sensor_supervisor PASS" severity note;
        wait;
    end process;
end architecture;
