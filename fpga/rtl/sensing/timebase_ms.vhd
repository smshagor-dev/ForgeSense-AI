library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity timebase_ms is
    generic (
        CLK_FREQ_HZ : positive := 27000000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        monotonic_ms : out unsigned(31 downto 0)
    );
end entity;

architecture rtl of timebase_ms is
    function divider(freq : positive) return positive is
    begin
        if freq < 1000 then
            return 1;
        end if;
        return freq / 1000;
    end function;

    constant CYCLES_PER_MS : positive := divider(CLK_FREQ_HZ);
    signal counter : natural range 0 to CYCLES_PER_MS - 1 := 0;
    signal time_ms : unsigned(31 downto 0) := (others => '0');
begin
    assert CLK_FREQ_HZ >= 1000
        report "CLK_FREQ_HZ must be at least 1 kHz"
        severity failure;

    assert (CLK_FREQ_HZ mod 1000) = 0
        report "millisecond timebase uses integer clock division"
        severity warning;

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                counter <= 0;
                time_ms <= (others => '0');
            elsif counter = CYCLES_PER_MS - 1 then
                counter <= 0;
                time_ms <= time_ms + 1;
            else
                counter <= counter + 1;
            end if;
        end if;
    end process;

    monotonic_ms <= time_ms;
end architecture;
