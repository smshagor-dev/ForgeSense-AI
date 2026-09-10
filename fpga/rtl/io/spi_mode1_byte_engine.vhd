library ieee;
use ieee.std_logic_1164.all;

entity spi_mode1_byte_engine is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        SPI_FREQ_HZ : positive := 2000000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        start : in std_logic;
        tx_byte : in std_logic_vector(7 downto 0);
        miso : in std_logic;
        ready : out std_logic;
        busy : out std_logic;
        done : out std_logic;
        rx_byte : out std_logic_vector(7 downto 0);
        sclk : out std_logic;
        mosi : out std_logic
    );
end entity;

architecture rtl of spi_mode1_byte_engine is
    function half_period_clks(freq : positive; spi_freq : positive) return positive is
        constant denominator : positive := 2 * spi_freq;
        variable result : natural;
    begin
        result := (freq + denominator - 1) / denominator;
        if result < 1 then
            return 1;
        end if;
        return result;
    end function;

    constant HALF_CLKS : positive := half_period_clks(CLK_FREQ_HZ, SPI_FREQ_HZ);
    signal active : std_logic := '0';
    signal clock_count : natural range 0 to HALF_CLKS - 1 := 0;
    signal bit_index : natural range 0 to 7 := 7;
    signal tx_latched : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_shift : std_logic_vector(7 downto 0) := (others => '0');
    signal sclk_reg : std_logic := '0';
    signal mosi_reg : std_logic := '0';
    signal done_reg : std_logic := '0';
begin
    assert (2 * SPI_FREQ_HZ) <= CLK_FREQ_HZ
        report "SPI_FREQ_HZ requires at least two FPGA clocks per SPI period"
        severity failure;

    process (clk)
    begin
        if rising_edge(clk) then
            done_reg <= '0';
            if rst = '1' then
                active <= '0';
                clock_count <= 0;
                bit_index <= 7;
                tx_latched <= (others => '0');
                rx_shift <= (others => '0');
                sclk_reg <= '0';
                mosi_reg <= '0';
            elsif active = '0' then
                sclk_reg <= '0';
                clock_count <= 0;
                if start = '1' then
                    active <= '1';
                    bit_index <= 7;
                    tx_latched <= tx_byte;
                    rx_shift <= (others => '0');
                    mosi_reg <= '0';
                end if;
            elsif clock_count = HALF_CLKS - 1 then
                clock_count <= 0;
                if sclk_reg = '0' then
                    -- CPOL=0/CPHA=1: change MOSI on the leading/rising edge.
                    sclk_reg <= '1';
                    mosi_reg <= tx_latched(bit_index);
                else
                    -- Sample MISO on the trailing/falling edge.
                    sclk_reg <= '0';
                    rx_shift(bit_index) <= miso;
                    if bit_index = 0 then
                        active <= '0';
                        mosi_reg <= '0';
                        done_reg <= '1';
                    else
                        bit_index <= bit_index - 1;
                    end if;
                end if;
            else
                clock_count <= clock_count + 1;
            end if;
        end if;
    end process;

    ready <= not active;
    busy <= active;
    done <= done_reg;
    rx_byte <= rx_shift;
    sclk <= sclk_reg;
    mosi <= mosi_reg;
end architecture;
