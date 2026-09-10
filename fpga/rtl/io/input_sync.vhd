library ieee;
use ieee.std_logic_1164.all;

entity input_sync is
    generic (RESET_VALUE : std_logic := '0');
    port (clk : in std_logic; rst : in std_logic; din : in std_logic; dout : out std_logic);
end entity;

architecture rtl of input_sync is
    signal ff1 : std_logic := RESET_VALUE;
    signal ff2 : std_logic := RESET_VALUE;
begin
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                ff1 <= RESET_VALUE;
                ff2 <= RESET_VALUE;
            else
                ff1 <= din;
                ff2 <= ff1;
            end if;
        end if;
    end process;
    dout <= ff2;
end architecture;
