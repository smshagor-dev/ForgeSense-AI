library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;
use work.sensor_device_math_pkg.all;

entity tb_sensor_device_math_pkg is
end entity;

architecture sim of tb_sensor_device_math_pkg is
begin
    process
        variable value16 : signed(15 downto 0);
    begin
        value16 := tmp117_raw_to_deci_c(to_signed(16#0C80#, 16));
        assert to_integer(value16) = 250
            report "TMP117 +25.0 C conversion mismatch"
            severity failure;

        value16 := tmp117_raw_to_deci_c(to_signed(-1280, 16));
        assert to_integer(value16) = -100
            report "TMP117 -10.0 C conversion mismatch"
            severity failure;

        value16 := adxl355_axis_to_milli_g(x"00", x"00", x"00");
        assert to_integer(value16) = 0
            report "ADXL355 zero conversion mismatch"
            severity failure;

        value16 := adxl355_axis_to_milli_g(x"0F", x"A0", x"00");
        assert to_integer(value16) = 998
            report "ADXL355 positive conversion mismatch"
            severity failure;

        value16 := adxl355_axis_to_milli_g(x"F0", x"60", x"00");
        assert to_integer(value16) = -998
            report "ADXL355 negative conversion mismatch"
            severity failure;

        assert ADS131M02_CURRENT_MA_NUMERATOR = 1000
            report "ADS131M02 current numerator changed"
            severity failure;
        assert ADS131M02_CURRENT_MA_DENOMINATOR = 2097152
            report "ADS131M02 current denominator changed"
            severity failure;

        report "tb_sensor_device_math_pkg PASS" severity note;
        stop;
        wait;
    end process;
end architecture;
