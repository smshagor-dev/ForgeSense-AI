library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity linear_sensor_adapter is
    generic (
        RAW_ZERO : integer := 0;
        GAIN_NUMERATOR : integer := 1;
        GAIN_DENOMINATOR : positive := 1;
        OUTPUT_OFFSET : integer := 0
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        raw_valid : in std_logic;
        raw_value : in signed(23 downto 0);
        normalized_valid : out std_logic;
        normalized_value : out signed(15 downto 0);
        numeric_saturated : out std_logic
    );
end entity;

architecture rtl of linear_sensor_adapter is
begin
    assert RAW_ZERO >= -8388608 and RAW_ZERO <= 8388607
        report "RAW_ZERO must fit the signed 24-bit sensor frontend contract"
        severity failure;

    process (clk)
        variable centered_v : signed(31 downto 0);
        variable product_v : signed(63 downto 0);
        variable scaled_v : signed(63 downto 0);
    begin
        if rising_edge(clk) then
            normalized_valid <= '0';
            numeric_saturated <= '0';
            if rst = '1' then
                normalized_value <= (others => '0');
            elsif raw_valid = '1' then
                centered_v := resize(raw_value, 32) - to_signed(RAW_ZERO, 32);
                product_v := centered_v * to_signed(GAIN_NUMERATOR, 32);
                scaled_v := (product_v / to_signed(GAIN_DENOMINATOR, 64)) +
                            to_signed(OUTPUT_OFFSET, 64);

                if scaled_v < to_signed(-32768, 64) then
                    normalized_value <= to_signed(-32768, 16);
                    numeric_saturated <= '1';
                elsif scaled_v > to_signed(32767, 64) then
                    normalized_value <= to_signed(32767, 16);
                    numeric_saturated <= '1';
                else
                    normalized_value <= resize(scaled_v, 16);
                end if;
                normalized_valid <= '1';
            end if;
        end if;
    end process;
end architecture;
