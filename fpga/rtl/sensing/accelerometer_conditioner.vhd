library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity accelerometer_conditioner is
    generic (
        ABS_LIMIT_MILLI_G : positive := 16000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_valid : in std_logic;
        sample_milli_g : in signed(15 downto 0);
        sample_error : in std_logic;
        conditioned_valid : out std_logic;
        conditioned_milli_g : out signed(15 downto 0);
        range_error : out std_logic;
        transport_error : out std_logic
    );
end entity;

architecture rtl of accelerometer_conditioner is
begin
    process (clk)
        variable value_i : integer;
    begin
        if rising_edge(clk) then
            conditioned_valid <= '0';
            range_error <= '0';
            transport_error <= '0';
            if rst = '1' then
                conditioned_milli_g <= (others => '0');
            elsif sample_valid = '1' then
                if sample_error = '1' then
                    transport_error <= '1';
                else
                    value_i := to_integer(sample_milli_g);
                    if value_i < -ABS_LIMIT_MILLI_G or value_i > ABS_LIMIT_MILLI_G then
                        range_error <= '1';
                    else
                        conditioned_milli_g <= sample_milli_g;
                        conditioned_valid <= '1';
                    end if;
                end if;
            end if;
        end if;
    end process;
end architecture;
