library ieee;
use ieee.std_logic_1164.all;
use std.env.all;

entity tb_spi_mode0_byte_engine is end entity;

architecture sim of tb_spi_mode0_byte_engine is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal start : std_logic := '0';
    signal tx_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal miso : std_logic;
    signal ready : std_logic;
    signal busy : std_logic;
    signal done : std_logic;
    signal rx_byte : std_logic_vector(7 downto 0);
    signal sclk : std_logic;
    signal mosi : std_logic;
    signal rising_count : natural range 0 to 8 := 0;
begin
    clk <= not clk after 50 ns;
    -- Loopback inversion makes bit-order errors visible: A5 must receive 5A.
    miso <= not mosi;

    dut : entity work.spi_mode0_byte_engine
        generic map (
            CLK_FREQ_HZ => 10000000,
            SPI_FREQ_HZ => 1000000
        )
        port map (
            clk => clk,
            rst => rst,
            start => start,
            tx_byte => tx_byte,
            miso => miso,
            ready => ready,
            busy => busy,
            done => done,
            rx_byte => rx_byte,
            sclk => sclk,
            mosi => mosi
        );

    process (sclk)
    begin
        if rising_edge(sclk) then
            if rising_count < 8 then
                rising_count <= rising_count + 1;
            end if;
        end if;
    end process;

    process
    begin
        wait for 300 ns;
        wait until rising_edge(clk);
        rst <= '0';
        wait until rising_edge(clk);

        assert ready = '1' and busy = '0' and sclk = '0'
            report "SPI engine did not reset to mode-0 idle"
            severity error;

        tx_byte <= x"A5";
        start <= '1';
        wait until rising_edge(clk);
        start <= '0';

        wait until done = '1';
        wait for 1 ns;

        assert rx_byte = x"5A"
            report "SPI mode-0 receive bit order or edge sampling is incorrect"
            severity error;
        assert rising_count = 8
            report "SPI transfer did not produce exactly eight rising sample edges"
            severity error;
        assert ready = '1' and busy = '0' and sclk = '0'
            report "SPI engine did not return to idle after one byte"
            severity error;

        report "tb_spi_mode0_byte_engine PASS" severity note;
        stop;
        wait;
    end process;
end architecture;
