library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package sensor_device_math_pkg is
    constant ADS131M02_CURRENT_MA_NUMERATOR : integer := 1000;
    constant ADS131M02_CURRENT_MA_DENOMINATOR : positive := 2097152;

    function tmp117_raw_to_deci_c(
        raw_value : signed(15 downto 0)
    ) return signed;

    function adxl355_axis_to_milli_g(
        b2 : std_logic_vector(7 downto 0);
        b1 : std_logic_vector(7 downto 0);
        b0 : std_logic_vector(7 downto 0)
    ) return signed;
end package;

package body sensor_device_math_pkg is
    function tmp117_raw_to_deci_c(
        raw_value : signed(15 downto 0)
    ) return signed is
        variable raw_i : integer;
        variable deci_i : integer;
    begin
        raw_i := to_integer(raw_value);
        if raw_i >= 0 then
            deci_i := (raw_i * 5 + 32) / 64;
        else
            deci_i := (raw_i * 5 - 32) / 64;
        end if;
        return to_signed(deci_i, 16);
    end function;

    function adxl355_axis_to_milli_g(
        b2 : std_logic_vector(7 downto 0);
        b1 : std_logic_vector(7 downto 0);
        b0 : std_logic_vector(7 downto 0)
    ) return signed is
        variable packed : signed(23 downto 0);
        variable raw20_i : integer;
        variable scaled_i : integer;
    begin
        packed := signed(b2 & b1 & b0);
        raw20_i := to_integer(shift_right(packed, 4));
        if raw20_i >= 0 then
            scaled_i := (raw20_i * 156 + 5000) / 10000;
        else
            scaled_i := (raw20_i * 156 - 5000) / 10000;
        end if;
        return to_signed(scaled_i, 16);
    end function;
end package body;
