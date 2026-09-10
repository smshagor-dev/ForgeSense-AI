library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity watchdog is
    generic (TIMEOUT_CYCLES : positive := 1000);
    port (clk : in std_logic; rst : in std_logic; kick : in std_logic; expired : out std_logic);
end entity;

architecture rtl of watchdog is
    signal counter : natural range 0 to TIMEOUT_CYCLES := 0;
    signal expired_i : std_logic := '0';
begin
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' or kick = '1' then
                counter <= 0;
                expired_i <= '0';
            elsif counter < TIMEOUT_CYCLES then
                if counter = TIMEOUT_CYCLES - 1 then
                    counter <= TIMEOUT_CYCLES;
                    expired_i <= '1';
                else
                    counter <= counter + 1;
                end if;
            else
                expired_i <= '1';
            end if;
        end if;
    end process;
    expired <= expired_i;
end architecture;
