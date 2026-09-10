library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_spi_mode1_byte_engine is end entity;

architecture sim of tb_spi_mode1_byte_engine is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal start : std_logic := '0';
    signal tx_byte : std_logic_vector(7 downto 0) := x"A5";
    signal miso : std_logic := '0';
    signal ready, busy, done : std_logic;
    signal rx_byte : std_logic_vector(7 downto 0);
    signal sclk, mosi : std_logic;
    signal slave_bits : std_logic_vector(7 downto 0) := x"3C";
    signal slave_index : integer range 0 to 7 := 7;
begin
    clk <= not clk after 5 ns;

    dut : entity work.spi_mode1_byte_engine
        generic map (CLK_FREQ_HZ => 10000000, SPI_FREQ_HZ => 1000000)
        port map (
            clk => clk, rst => rst, start => start, tx_byte => tx_byte,
            miso => miso, ready => ready, busy => busy, done => done,
            rx_byte => rx_byte, sclk => sclk, mosi => mosi
        );

    process(sclk)
    begin
        if rising_edge(sclk) then
            miso <= slave_bits(slave_index);
            if slave_index > 0 then slave_index <= slave_index - 1; end if;
        end if;
    end process;

    process
    begin
        wait for 30 ns; rst <= '0';
        wait until rising_edge(clk) and ready = '1';
        start <= '1'; wait until rising_edge(clk); start <= '0';
        wait until rising_edge(clk) and done = '1'; wait for 1 ns;
        assert rx_byte = x"3C" report "mode-1 receive byte mismatch" severity error;
        assert sclk = '0' report "mode-1 clock must return low when idle" severity error;
        assert ready = '1' report "mode-1 engine did not return ready" severity error;
        report "tb_spi_mode1_byte_engine PASS" severity note;
        stop; wait;
    end process;
end architecture;
