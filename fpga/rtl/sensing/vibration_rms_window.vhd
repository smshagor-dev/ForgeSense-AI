library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity vibration_rms_window is
    generic (
        WINDOW_SAMPLES : positive := 64
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_valid : in std_logic;
        conditioned_milli_g : in signed(15 downto 0);
        rms_update : out std_logic;
        rms_milli_g : out unsigned(15 downto 0)
    );
end entity;

architecture rtl of vibration_rms_window is
    signal sum_squares : unsigned(47 downto 0) := (others => '0');
    signal sample_count : natural range 0 to WINDOW_SAMPLES - 1 := 0;

    function isqrt48(value : unsigned(47 downto 0)) return unsigned is
        variable root : unsigned(15 downto 0) := (others => '0');
        variable trial : unsigned(15 downto 0);
        variable square : unsigned(31 downto 0);
    begin
        for i in 15 downto 0 loop
            trial := root;
            trial(i) := '1';
            square := trial * trial;
            if resize(square, 48) <= value then
                root := trial;
            end if;
        end loop;
        return root;
    end function;
begin
    process (clk)
        variable sample_i : integer;
        variable square_i : integer;
        variable next_sum : unsigned(47 downto 0);
        variable mean_square : unsigned(47 downto 0);
    begin
        if rising_edge(clk) then
            rms_update <= '0';
            if rst = '1' then
                sum_squares <= (others => '0');
                sample_count <= 0;
                rms_milli_g <= (others => '0');
            elsif sample_valid = '1' then
                sample_i := to_integer(conditioned_milli_g);
                square_i := sample_i * sample_i;
                next_sum := sum_squares + to_unsigned(square_i, 48);

                if sample_count = WINDOW_SAMPLES - 1 then
                    mean_square := next_sum / WINDOW_SAMPLES;
                    rms_milli_g <= isqrt48(mean_square);
                    rms_update <= '1';
                    sum_squares <= (others => '0');
                    sample_count <= 0;
                else
                    sum_squares <= next_sum;
                    sample_count <= sample_count + 1;
                end if;
            end if;
        end if;
    end process;
end architecture;
