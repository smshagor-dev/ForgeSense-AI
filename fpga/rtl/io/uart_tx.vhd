library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity uart_tx is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        BAUD_RATE : positive := 115200
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        data_valid : in std_logic;
        data_byte : in std_logic_vector(7 downto 0);
        ready : out std_logic;
        tx_serial : out std_logic
    );
end entity;

architecture rtl of uart_tx is
    function clocks_per_bit(freq : positive; baud : positive) return positive is
    begin
        if baud >= freq then
            return 1;
        end if;
        return freq / baud;
    end function;

    constant CLKS_PER_BIT : positive := clocks_per_bit(CLK_FREQ_HZ, BAUD_RATE);
    type state_t is (IDLE, START_BIT, DATA_BITS, STOP_BIT);
    signal state : state_t := IDLE;
    signal clock_count : natural range 0 to CLKS_PER_BIT - 1 := 0;
    signal bit_index : natural range 0 to 7 := 0;
    signal data_latched : std_logic_vector(7 downto 0) := (others => '0');
    signal tx_reg : std_logic := '1';
begin
    assert CLKS_PER_BIT >= 4
        report "UART clock must provide at least 4 clocks per bit"
        severity failure;

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state <= IDLE;
                clock_count <= 0;
                bit_index <= 0;
                data_latched <= (others => '0');
                tx_reg <= '1';
            else
                case state is
                    when IDLE =>
                        tx_reg <= '1';
                        clock_count <= 0;
                        bit_index <= 0;
                        if data_valid = '1' then
                            data_latched <= data_byte;
                            tx_reg <= '0';
                            state <= START_BIT;
                        end if;

                    when START_BIT =>
                        tx_reg <= '0';
                        if clock_count = CLKS_PER_BIT - 1 then
                            clock_count <= 0;
                            tx_reg <= data_latched(0);
                            state <= DATA_BITS;
                        else
                            clock_count <= clock_count + 1;
                        end if;

                    when DATA_BITS =>
                        tx_reg <= data_latched(bit_index);
                        if clock_count = CLKS_PER_BIT - 1 then
                            clock_count <= 0;
                            if bit_index = 7 then
                                bit_index <= 0;
                                tx_reg <= '1';
                                state <= STOP_BIT;
                            else
                                bit_index <= bit_index + 1;
                            end if;
                        else
                            clock_count <= clock_count + 1;
                        end if;

                    when STOP_BIT =>
                        tx_reg <= '1';
                        if clock_count = CLKS_PER_BIT - 1 then
                            clock_count <= 0;
                            state <= IDLE;
                        else
                            clock_count <= clock_count + 1;
                        end if;
                end case;
            end if;
        end if;
    end process;

    ready <= '1' when state = IDLE else '0';
    tx_serial <= tx_reg;
end architecture;
