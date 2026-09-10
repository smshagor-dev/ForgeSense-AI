library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity digital_temperature_adapter is
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_valid : in std_logic;
        temperature_deci_c_in : in signed(15 downto 0);
        sample_error : in std_logic;
        normalized_valid : out std_logic;
        normalized_temperature_deci_c : out signed(15 downto 0);
        diagnostic_error : out std_logic
    );
end entity;

architecture rtl of digital_temperature_adapter is
begin
    process (clk)
    begin
        if rising_edge(clk) then
            normalized_valid <= '0';
            diagnostic_error <= '0';
            if rst = '1' then
                normalized_temperature_deci_c <= (others => '0');
            elsif sample_valid = '1' then
                if sample_error = '1' then
                    diagnostic_error <= '1';
                else
                    normalized_temperature_deci_c <= temperature_deci_c_in;
                    normalized_valid <= '1';
                end if;
            end if;
        end if;
    end process;
end architecture;
