library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity uart_rx is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        BAUD_RATE : positive := 115200
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        rx_serial : in std_logic;
        data_valid : out std_logic;
        data_byte : out std_logic_vector(7 downto 0);
        framing_error : out std_logic
    );
end entity;

architecture rtl of uart_rx is
    function clocks_per_bit(freq : positive; baud : positive) return positive is
    begin
        if baud >= freq then
            return 1;
        end if;
        return freq / baud;
    end function;

    constant CLKS_PER_BIT : positive := clocks_per_bit(CLK_FREQ_HZ, BAUD_RATE);
    constant HALF_BIT : natural := CLKS_PER_BIT / 2;

    type state_t is (IDLE, START_CHECK, DATA_BITS, STOP_CHECK);
    signal state : state_t := IDLE;
    signal rx_meta : std_logic := '1';
    signal rx_sync : std_logic := '1';
    signal clock_count : natural range 0 to CLKS_PER_BIT - 1 := 0;
    signal bit_index : natural range 0 to 7 := 0;
    signal data_latched : std_logic_vector(7 downto 0) := (others => '0');
begin
    assert CLKS_PER_BIT >= 4
        report "UART clock must provide at least 4 clocks per bit"
        severity failure;

    process (clk)
    begin
        if rising_edge(clk) then
            rx_meta <= rx_serial;
            rx_sync <= rx_meta;

            data_valid <= '0';
            framing_error <= '0';

            if rst = '1' then
                state <= IDLE;
                clock_count <= 0;
                bit_index <= 0;
                data_latched <= (others => '0');
                data_byte <= (others => '0');
            else
                case state is
                    when IDLE =>
                        clock_count <= 0;
                        bit_index <= 0;
                        if rx_sync = '0' then
                            state <= START_CHECK;
                        end if;

                    when START_CHECK =>
                        if clock_count = HALF_BIT then
                            if rx_sync = '0' then
                                clock_count <= 0;
                                state <= DATA_BITS;
                            else
                                state <= IDLE;
                            end if;
                        else
                            clock_count <= clock_count + 1;
                        end if;

                    when DATA_BITS =>
                        if clock_count = CLKS_PER_BIT - 1 then
                            clock_count <= 0;
                            data_latched(bit_index) <= rx_sync;
                            if bit_index = 7 then
                                bit_index <= 0;
                                state <= STOP_CHECK;
                            else
                                bit_index <= bit_index + 1;
                            end if;
                        else
                            clock_count <= clock_count + 1;
                        end if;

                    when STOP_CHECK =>
                        if clock_count = CLKS_PER_BIT - 1 then
                            clock_count <= 0;
                            if rx_sync = '1' then
                                data_byte <= data_latched;
                                data_valid <= '1';
                            else
                                framing_error <= '1';
                            end if;
                            state <= IDLE;
                        else
                            clock_count <= clock_count + 1;
                        end if;
                end case;
            end if;
        end if;
    end process;
end architecture;
