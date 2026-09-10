library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity status_link_tx is
    port (
        clk : in std_logic;
        rst : in std_logic;
        status_trigger : in std_logic;
        timestamp_ms : in unsigned(31 downto 0);
        state_code : in std_logic_vector(2 downto 0);
        control_flags : in unsigned(7 downto 0);
        safety_flags : in unsigned(15 downto 0);
        tx_ready : in std_logic;
        tx_valid : out std_logic;
        tx_byte : out std_logic_vector(7 downto 0)
    );
end entity;

architecture rtl of status_link_tx is
    signal busy : std_logic := '0';
    signal pending : std_logic := '0';
    signal byte_index : natural range 0 to 17 := 0;
    signal sequence : unsigned(15 downto 0) := (others => '0');
    signal timestamp_latched : unsigned(31 downto 0) := (others => '0');
    signal state_latched : unsigned(7 downto 0) := (others => '0');
    signal control_latched : unsigned(7 downto 0) := (others => '0');
    signal safety_latched : unsigned(15 downto 0) := (others => '0');
    signal crc_reg : unsigned(15 downto 0) := to_unsigned(16#FFFF#, 16);
    signal byte_i : std_logic_vector(7 downto 0);
begin
    process (byte_index, sequence, timestamp_latched, state_latched,
             control_latched, safety_latched, crc_reg)
    begin
        byte_i <= x"00";
        case byte_index is
            when 0 => byte_i <= x"A5";
            when 1 => byte_i <= x"5A";
            when 2 => byte_i <= x"01";
            when 3 => byte_i <= x"30";
            when 4 => byte_i <= std_logic_vector(sequence(7 downto 0));
            when 5 => byte_i <= std_logic_vector(sequence(15 downto 8));
            when 6 => byte_i <= x"04";
            when 7 => byte_i <= x"00";
            when 8 => byte_i <= std_logic_vector(timestamp_latched(7 downto 0));
            when 9 => byte_i <= std_logic_vector(timestamp_latched(15 downto 8));
            when 10 => byte_i <= std_logic_vector(timestamp_latched(23 downto 16));
            when 11 => byte_i <= std_logic_vector(timestamp_latched(31 downto 24));
            when 12 => byte_i <= std_logic_vector(state_latched);
            when 13 => byte_i <= std_logic_vector(control_latched);
            when 14 => byte_i <= std_logic_vector(safety_latched(7 downto 0));
            when 15 => byte_i <= std_logic_vector(safety_latched(15 downto 8));
            when 16 => byte_i <= std_logic_vector(crc_reg(7 downto 0));
            when 17 => byte_i <= std_logic_vector(crc_reg(15 downto 8));
            when others => byte_i <= x"00";
        end case;
    end process;

    process (clk)
        procedure capture_status is
        begin
            timestamp_latched <= timestamp_ms;
            state_latched <= resize(unsigned(state_code), 8);
            control_latched <= control_flags;
            safety_latched <= safety_flags;
            crc_reg <= to_unsigned(16#FFFF#, 16);
            byte_index <= 0;
            busy <= '1';
        end procedure;
    begin
        if rising_edge(clk) then
            if rst = '1' then
                busy <= '0';
                pending <= '0';
                byte_index <= 0;
                sequence <= (others => '0');
                timestamp_latched <= (others => '0');
                state_latched <= (others => '0');
                control_latched <= (others => '0');
                safety_latched <= (others => '0');
                crc_reg <= to_unsigned(16#FFFF#, 16);
            else
                if status_trigger = '1' then
                    if busy = '0' then
                        pending <= '0';
                        capture_status;
                    else
                        pending <= '1';
                    end if;
                elsif busy = '0' and pending = '1' then
                    pending <= '0';
                    capture_status;
                end if;

                if busy = '1' and tx_ready = '1' then
                    if byte_index >= 2 and byte_index <= 15 then
                        crc_reg <= crc16_next(crc_reg, byte_i);
                    end if;

                    if byte_index = 17 then
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
