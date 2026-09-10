library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity sensor_link_tx is
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_trigger : in std_logic;
        timestamp_ms : in unsigned(31 downto 0);
        temperature_deci_c : in signed(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        sensor_flags : in unsigned(15 downto 0);
        tx_ready : in std_logic;
        tx_valid : out std_logic;
        tx_byte : out std_logic_vector(7 downto 0);
        sample_dropped : out std_logic
    );
end entity;

architecture rtl of sensor_link_tx is
    signal busy : std_logic := '0';
    signal byte_index : natural range 0 to 21 := 0;
    signal sequence : unsigned(15 downto 0) := (others => '0');
    signal timestamp_latched : unsigned(31 downto 0) := (others => '0');
    signal temperature_latched : signed(15 downto 0) := (others => '0');
    signal vibration_latched : unsigned(15 downto 0) := (others => '0');
    signal current_latched : unsigned(15 downto 0) := (others => '0');
    signal flags_latched : unsigned(15 downto 0) := (others => '0');
    signal crc_reg : unsigned(15 downto 0) := to_unsigned(16#FFFF#, 16);
    signal byte_i : std_logic_vector(7 downto 0);
begin
    process (
        byte_index,
        sequence,
        timestamp_latched,
        temperature_latched,
        vibration_latched,
        current_latched,
        flags_latched,
        crc_reg
    )
    begin
        byte_i <= x"00";
        case byte_index is
            when 0 => byte_i <= x"A5";
            when 1 => byte_i <= x"5A";
            when 2 => byte_i <= x"01";
            when 3 => byte_i <= x"11";
            when 4 => byte_i <= std_logic_vector(sequence(7 downto 0));
            when 5 => byte_i <= std_logic_vector(sequence(15 downto 8));
            when 6 => byte_i <= x"08";
            when 7 => byte_i <= x"00";
            when 8 => byte_i <= std_logic_vector(timestamp_latched(7 downto 0));
            when 9 => byte_i <= std_logic_vector(timestamp_latched(15 downto 8));
            when 10 => byte_i <= std_logic_vector(timestamp_latched(23 downto 16));
            when 11 => byte_i <= std_logic_vector(timestamp_latched(31 downto 24));
            when 12 => byte_i <= std_logic_vector(temperature_latched(7 downto 0));
            when 13 => byte_i <= std_logic_vector(temperature_latched(15 downto 8));
            when 14 => byte_i <= std_logic_vector(vibration_latched(7 downto 0));
            when 15 => byte_i <= std_logic_vector(vibration_latched(15 downto 8));
            when 16 => byte_i <= std_logic_vector(current_latched(7 downto 0));
            when 17 => byte_i <= std_logic_vector(current_latched(15 downto 8));
            when 18 => byte_i <= std_logic_vector(flags_latched(7 downto 0));
            when 19 => byte_i <= std_logic_vector(flags_latched(15 downto 8));
            when 20 => byte_i <= std_logic_vector(crc_reg(7 downto 0));
            when 21 => byte_i <= std_logic_vector(crc_reg(15 downto 8));
            when others => byte_i <= x"00";
        end case;
    end process;

    process (clk)
    begin
        if rising_edge(clk) then
            sample_dropped <= '0';

            if rst = '1' then
                busy <= '0';
                byte_index <= 0;
                sequence <= (others => '0');
                timestamp_latched <= (others => '0');
                temperature_latched <= (others => '0');
                vibration_latched <= (others => '0');
                current_latched <= (others => '0');
                flags_latched <= (others => '0');
                crc_reg <= to_unsigned(16#FFFF#, 16);
            else
                if sample_trigger = '1' then
                    if busy = '0' then
                        busy <= '1';
                        byte_index <= 0;
                        timestamp_latched <= timestamp_ms;
                        temperature_latched <= temperature_deci_c;
                        vibration_latched <= vibration_milli_g;
                        current_latched <= current_milli_a;
                        flags_latched <= sensor_flags;
                        crc_reg <= to_unsigned(16#FFFF#, 16);
                    else
                        sample_dropped <= '1';
                    end if;
                end if;

                if busy = '1' and tx_ready = '1' then
                    if byte_index >= 2 and byte_index <= 19 then
                        crc_reg <= crc16_next(crc_reg, byte_i);
                    end if;

                    if byte_index = 21 then
                        busy <= '0';
                        byte_index <= 0;
                        sequence <= sequence + 1;
                    else
                        byte_index <= byte_index + 1;
                    end if;
                end if;
            end if;
        end if;
    end process;

    tx_valid <= busy;
    tx_byte <= byte_i;
end architecture;
