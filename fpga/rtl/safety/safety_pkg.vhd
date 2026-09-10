library ieee;
use ieee.std_logic_1164.all;

package safety_pkg is
    type safety_state_t is (ST_STARTUP, ST_RUN, ST_WARNING, ST_SHUTDOWN, ST_FAULT_LATCHED, ST_RECOVERY);
    function state_to_slv(state : safety_state_t) return std_logic_vector;
end package;

package body safety_pkg is
    function state_to_slv(state : safety_state_t) return std_logic_vector is
    begin
        case state is
            when ST_STARTUP       => return "000";
            when ST_RUN           => return "001";
            when ST_WARNING       => return "010";
            when ST_SHUTDOWN      => return "011";
            when ST_FAULT_LATCHED => return "100";
            when ST_RECOVERY      => return "101";
        end case;
    end function;
end package body;
