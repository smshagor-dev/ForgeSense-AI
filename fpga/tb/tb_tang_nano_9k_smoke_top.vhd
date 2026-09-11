library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_tang_nano_9k_smoke_top is
end entity;

architecture tb of tb_tang_nano_9k_smoke_top is
    constant CLK_PERIOD : time := 37.037 ns;
    constant UART_BIT_TIME : time := 8.667 us;

    signal clk : std_logic := '0';
    signal reset_n : std_logic := '0';
    signal uart_rx : std_logic := '1';
    signal uart_tx : std_logic;
    signal tmp_scl : std_logic := 'H';
    signal tmp_sda : std_logic := 'H';
    signal adxl_cs_n, adxl_sclk, adxl_mosi : std_logic;
    signal ads_cs_n, ads_sclk, ads_din : std_logic;
    signal load_enable : std_logic;
    signal echo_seen : std_logic := '0';
    signal echoed_byte : std_logic_vector(7 downto 0) := (others => '0');

    procedure uart_send(signal line : out std_logic; constant data : std_logic_vector(7 downto 0)) is
    begin
        line <= '0';
        wait for UART_BIT_TIME;
        for i in 0 to 7 loop
            line <= data(i);
            wait for UART_BIT_TIME;
        end loop;
        line <= '1';
        wait for UART_BIT_TIME;
    end procedure;

    procedure uart_receive(signal line : in std_logic; variable data : out std_logic_vector(7 downto 0)) is
    begin
        wait until line = '0';
        wait for UART_BIT_TIME + UART_BIT_TIME / 2;
        for i in 0 to 7 loop
            data(i) := line;
            wait for UART_BIT_TIME;
        end loop;
        assert line = '1' report "UART stop bit was not high" severity failure;
    end procedure;
begin
    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.forgesense_tang_nano_9k_smoke_top
        generic map (
            CLK_FREQ_HZ => 27000000,
            UART_BAUD_RATE => 115200
        )
        port map (
            clk_27m_i => clk,
            reset_n_i => reset_n,
            esp32_uart_rx_i => uart_rx,
            esp32_uart_tx_o => uart_tx,
            tmp_scl_io => tmp_scl,
            tmp_sda_io => tmp_sda,
            adxl_drdy_i => '0',
            adxl_miso_i => '0',
            adxl_cs_n_o => adxl_cs_n,
            adxl_sclk_o => adxl_sclk,
            adxl_mosi_o => adxl_mosi,
            ads_drdy_n_i => '1',
            ads_dout_i => '0',
            ads_cs_n_o => ads_cs_n,
            ads_sclk_o => ads_sclk,
            ads_din_o => ads_din,
            analog_hard_trip_i => '0',
            estop_sense_i => '0',
            recovery_req_i => '0',
            load_enable_o => load_enable
        );

    receiver : process
        variable data : std_logic_vector(7 downto 0);
    begin
        wait until reset_n = '1';
        uart_receive(uart_tx, data);
        echoed_byte <= data;
        echo_seen <= '1';
        wait;
    end process;

    stimulus : process
    begin
        wait for 20 * CLK_PERIOD;
        reset_n <= '1';
        wait for 20 * CLK_PERIOD;

        assert load_enable = '0' report "smoke image authorized load output" severity failure;
        assert adxl_cs_n = '1' and ads_cs_n = '1' report "sensor chip select active in smoke image" severity failure;
        assert adxl_sclk = '0' and ads_sclk = '0' report "sensor clock active in smoke image" severity failure;
        assert tmp_scl /= '0' and tmp_sda /= '0' report "I2C line driven low in smoke image" severity failure;

        uart_send(uart_rx, x"A6");
        wait until echo_seen = '1';
        assert echoed_byte = x"A6" report "UART smoke echo mismatch" severity failure;
        assert load_enable = '0' report "load output changed during UART smoke test" severity failure;

        report "tb_tang_nano_9k_smoke_top PASS" severity note;
        stop;
        wait;
    end process;
end architecture;
