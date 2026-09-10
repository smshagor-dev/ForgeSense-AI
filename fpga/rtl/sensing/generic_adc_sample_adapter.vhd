library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity generic_adc_sample_adapter is
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_valid : in std_logic;
        sample_signed24 : in signed(23 downto 0);
        sample_error : in std_logic;
        raw_valid : out std_logic;
        raw_value : out signed(23 downto 0);
        diagnostic_error : out std_logic
    );
end entity;

architecture rtl of generic_adc_sample_adapter is
begin
    process (clk)
    begin
        if rising_edge(clk) then
            raw_valid <= '0';
            diagnostic_error <= '0';
            if rst = '1' then
                raw_value <= (others => '0');
            elsif sample_valid = '1' then
                if sample_error = '1' then
                    diagnostic_error <= '1';
                else
                    raw_value <= sample_signed24;
                    raw_valid <= '1';
                end if;
            end if;
        end if;
    end process;
end architecture;
