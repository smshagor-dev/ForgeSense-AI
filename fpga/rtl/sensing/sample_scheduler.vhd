library ieee;
use ieee.std_logic_1164.all;

entity sample_scheduler is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        SAMPLE_RATE_HZ : positive := 10
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_tick : out std_logic
    );
end entity;

architecture rtl of sample_scheduler is
    function divider(freq : positive; rate : positive) return positive is
    begin
        if rate >= freq then
            return 1;
        end if;
        return freq / rate;
    end function;

    constant DIVISOR : positive := divider(CLK_FREQ_HZ, SAMPLE_RATE_HZ);
    signal counter : natural range 0 to DIVISOR - 1 := 0;
begin
    assert SAMPLE_RATE_HZ <= CLK_FREQ_HZ
        report "SAMPLE_RATE_HZ must not exceed CLK_FREQ_HZ"
        severity failure;

    assert (CLK_FREQ_HZ mod SAMPLE_RATE_HZ) = 0
        report "sample scheduler uses integer clock division; requested rate is rounded"
        severity warning;

    process (clk)
    begin
        if rising_edge(clk) then
            sample_tick <= '0';
            if rst = '1' then
                counter <= 0;
            elsif counter = DIVISOR - 1 then
                counter <= 0;
                sample_tick <= '1';
            else
                counter <= counter + 1;
            end if;
        end if;
    end process;
end architecture;
