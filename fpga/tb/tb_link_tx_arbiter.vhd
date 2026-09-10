library ieee;
use ieee.std_logic_1164.all;

entity tb_link_tx_arbiter is
end entity;

architecture sim of tb_link_tx_arbiter is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal status_valid : std_logic := '0';
    signal status_byte : std_logic_vector(7 downto 0) := x"30";
    signal status_ready : std_logic;
    signal sensor_valid : std_logic := '0';
    signal sensor_byte : std_logic_vector(7 downto 0) := x"11";
    signal sensor_ready : std_logic;
    signal uart_ready : std_logic := '1';
    signal uart_valid : std_logic;
    signal uart_byte : std_logic_vector(7 downto 0);
begin
    clk <= not clk after 5 ns;

    dut : entity work.link_tx_arbiter
        port map (
            clk => clk,
            rst => rst,
            status_valid => status_valid,
            status_byte => status_byte,
            status_ready => status_ready,
            sensor_valid => sensor_valid,
            sensor_byte => sensor_byte,
            sensor_ready => sensor_ready,
            uart_ready => uart_ready,
            uart_valid => uart_valid,
            uart_byte => uart_byte
        );

    stimulus : process
    begin
        wait for 20 ns;
        wait until rising_edge(clk);
        rst <= '0';
        status_valid <= '1';
        sensor_valid <= '1';

        wait until rising_edge(clk);
        wait for 1 ns;
        assert status_ready = '1' and sensor_ready = '0'
            report "status did not receive priority"
            severity failure;
        assert uart_valid = '1' and uart_byte = x"30"
            report "status byte not selected"
            severity failure;

        status_valid <= '0';
        wait until rising_edge(clk);
        wait until rising_edge(clk);
        wait for 1 ns;
        assert sensor_ready = '1'
            report "sensor stream was not granted after status completed"
            severity failure;
        assert uart_valid = '1' and uart_byte = x"11"
            report "sensor byte not selected"
            severity failure;

        report "tb_link_tx_arbiter PASS" severity note;
        wait;
    end process;
end architecture;
