library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package sensor_phy_diagnostics_pkg is
    constant PHY_DIAG_NO_SAMPLE            : natural := 0;
    constant PHY_DIAG_RAW_RANGE            : natural := 1;
    constant PHY_DIAG_CALIBRATION_INVALID  : natural := 2;
    constant PHY_DIAG_NUMERIC_SATURATION   : natural := 3;
    constant PHY_DIAG_VIB_WINDOW_NOT_READY : natural := 4;
    constant PHY_DIAG_VIB_RANGE            : natural := 5;
end package;
