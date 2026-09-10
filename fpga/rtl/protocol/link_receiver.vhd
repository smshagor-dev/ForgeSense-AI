library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity link_receiver is
    port (
        clk : in std_logic;
        rst : in std_logic;
        rx_valid : in std_logic;
        rx_byte : in std_logic_vector(7 downto 0);
        frame_valid : out std_logic;
        frame_rejected : out std_logic;
        sequence_number : out unsigned(15 downto 0);
        timestamp_ms : out unsigned(31 downto 0);
        model_id : out unsigned(15 downto 0);
        model_version : out unsigned(15 downto 0);
        feature_schema_version : out unsigned(15 downto 0);
        observation_valid_flag : out std_logic;
        anomaly_q15 : out unsigned(15 downto 0);
        health_class : out unsigned(7 downto 0);
        confidence_q8 : out unsigned(7 downto 0);
        inference_age_ms : out unsigned(15 downto 0)
    );
end entity;

architecture rtl of link_receiver is
    signal byte_index : natural range 0 to 27 := 0;
    signal crc_reg : unsigned(15 downto 0) := to_unsigned(16#FFFF#, 16);
    signal crc_rx_low : unsigned(7 downto 0) := (others => '0');
    signal sequence_i : unsigned(15 downto 0) := (others => '0');
    signal timestamp_i : unsigned(31 downto 0) := (others => '0');
    signal model_id_i : unsigned(15 downto 0) := (others => '0');
    signal model_version_i : unsigned(15 downto 0) := (others => '0');
    signal schema_i : unsigned(15 downto 0) := (others => '0');
    signal flags_i : unsigned(15 downto 0) := (others => '0');
    signal anomaly_i : unsigned(15 downto 0) := (others => '0');
    signal health_i : unsigned(7 downto 0) := (others => '0');
    signal confidence_i : unsigned(7 downto 0) := (others => '0');
    signal age_i : unsigned(15 downto 0) := (others => '0');

    function restart_index(byte_value : std_logic_vector(7 downto 0)) return natural is
    begin
        if byte_value = x"A5" then
            return 1;
        end if;
        return 0;
    end function;
begin
    process (clk)
        variable received_crc : unsigned(15 downto 0);
        variable invalid_field : boolean;
    begin
        if rising_edge(clk) then
            frame_valid <= '0';
            frame_rejected <= '0';
            if rst = '1' then
                byte_index <= 0;
                crc_reg <= to_unsigned(16#FFFF#, 16);
                sequence_i <= (others => '0');
                timestamp_i <= (others => '0');
                model_id_i <= (others => '0');
                model_version_i <= (others => '0');
                schema_i <= (others => '0');
                flags_i <= (others => '0');
                anomaly_i <= (others => '0');
                health_i <= (others => '0');
                confidence_i <= (others => '0');
                age_i <= (others => '0');
            elsif rx_valid = '1' then
                invalid_field := false;
                case byte_index is
                    when 0 =>
                        if rx_byte = x"A5" then
                            byte_index <= 1;
                        end if;
                    when 1 =>
                        if rx_byte = x"5A" then
                            byte_index <= 2;
                            crc_reg <= to_unsigned(16#FFFF#, 16);
                        else
                            byte_index <= restart_index(rx_byte);
                        end if;
                    when 2 => invalid_field := rx_byte /= x"01";
                    when 3 => invalid_field := rx_byte /= x"10";
                    when 4 => sequence_i(7 downto 0) <= unsigned(rx_byte);
                    when 5 => sequence_i(15 downto 8) <= unsigned(rx_byte);
                    when 6 => invalid_field := rx_byte /= x"0E";
                    when 7 => invalid_field := rx_byte /= x"00";
                    when 8 => timestamp_i(7 downto 0) <= unsigned(rx_byte);
                    when 9 => timestamp_i(15 downto 8) <= unsigned(rx_byte);
                    when 10 => timestamp_i(23 downto 16) <= unsigned(rx_byte);
                    when 11 => timestamp_i(31 downto 24) <= unsigned(rx_byte);
                    when 12 => model_id_i(7 downto 0) <= unsigned(rx_byte);
                    when 13 => model_id_i(15 downto 8) <= unsigned(rx_byte);
                    when 14 => model_version_i(7 downto 0) <= unsigned(rx_byte);
                    when 15 => model_version_i(15 downto 8) <= unsigned(rx_byte);
                    when 16 => schema_i(7 downto 0) <= unsigned(rx_byte);
                    when 17 => schema_i(15 downto 8) <= unsigned(rx_byte);
                    when 18 => flags_i(7 downto 0) <= unsigned(rx_byte);
                    when 19 => flags_i(15 downto 8) <= unsigned(rx_byte);
                    when 20 => anomaly_i(7 downto 0) <= unsigned(rx_byte);
                    when 21 => anomaly_i(15 downto 8) <= unsigned(rx_byte);
                    when 22 =>
                        health_i <= unsigned(rx_byte);
                        invalid_field := unsigned(rx_byte) > to_unsigned(3, 8);
                    when 23 => confidence_i <= unsigned(rx_byte);
                    when 24 => age_i(7 downto 0) <= unsigned(rx_byte);
                    when 25 => age_i(15 downto 8) <= unsigned(rx_byte);
                    when 26 => crc_rx_low <= unsigned(rx_byte);
                    when 27 =>
                        received_crc := unsigned(rx_byte) & crc_rx_low;
                        if received_crc = crc_reg then
                            frame_valid <= '1';
                        else
                            frame_rejected <= '1';
                        end if;
                        byte_index <= 0;
                    when others => byte_index <= 0;
                end case;

                if byte_index >= 2 and byte_index <= 25 then
                    crc_reg <= crc16_next(crc_reg, rx_byte);
                end if;

                if invalid_field then
                    frame_rejected <= '1';
                    byte_index <= restart_index(rx_byte);
                    crc_reg <= to_unsigned(16#FFFF#, 16);
                elsif byte_index >= 2 and byte_index < 27 then
                    byte_index <= byte_index + 1;
                end if;
            end if;
        end if;
    end process;

    sequence_number <= sequence_i;
    timestamp_ms <= timestamp_i;
    model_id <= model_id_i;
    model_version <= model_version_i;
    feature_schema_version <= schema_i;
    observation_valid_flag <= flags_i(0);
    anomaly_q15 <= anomaly_i;
    health_class <= health_i;
    confidence_q8 <= confidence_i;
    inference_age_ms <= age_i;
end architecture;
