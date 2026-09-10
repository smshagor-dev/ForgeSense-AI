library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package crc16_ccitt_pkg is
    function crc16_next(
        crc_in : unsigned(15 downto 0);
        data_byte : std_logic_vector(7 downto 0)
    ) return unsigned;
end package;

package body crc16_ccitt_pkg is
    function crc16_next(
        crc_in : unsigned(15 downto 0);
        data_byte : std_logic_vector(7 downto 0)
    ) return unsigned is
        variable crc : unsigned(15 downto 0) := crc_in;
    begin
        crc := crc xor shift_left(resize(unsigned(data_byte), 16), 8);
        for bit_index in 0 to 7 loop
            if crc(15) = '1' then
                crc := shift_left(crc, 1) xor to_unsigned(16#1021#, 16);
            else
                crc := shift_left(crc, 1);
            end if;
        end loop;
        return crc;
    end function;
end package body;
