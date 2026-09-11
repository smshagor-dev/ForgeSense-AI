library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity calibration_diag_tx is
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_trigger : in std_logic;
        timestamp_ms : in unsigned(31 downto 0);
        ads_ch0_raw : in signed(23 downto 0);
        ads_ch1_raw : in signed(23 downto 0);
        tmp_deci_c : in signed(15 downto 0);
        adxl_x_milli_g : in signed(15 downto 0);
        adxl_y_milli_g : in signed(15 downto 0);
        adxl_z_milli_g : in signed(15 downto 0);
        diagnostic_flags : in unsigned(15 downto 0);
        tx_ready : in std_logic;
        tx_valid : out std_logic;
        tx_byte : out std_logic_vector(7 downto 0);
        sample_dropped : out std_logic
    );
end entity;

architecture rtl of calibration_diag_tx is
    constant FRAME_LAST_INDEX : natural := 29;
    signal busy : std_logic := '0';
    signal byte_index : natural range 0 to FRAME_LAST_INDEX := 0;
    signal sequence : unsigned(15 downto 0) := (others => '0');
    signal timestamp_latched : unsigned(31 downto 0) := (others => '0');
    signal ads_ch0_latched, ads_ch1_latched : signed(23 downto 0) := (others => '0');
    signal tmp_latched : signed(15 downto 0) := (others => '0');
    signal adxl_x_latched, adxl_y_latched, adxl_z_latched : signed(15 downto 0) := (others => '0');
    signal flags_latched : unsigned(15 downto 0) := (others => '0');
    signal crc_reg : unsigned(15 downto 0) := to_unsigned(16#FFFF#, 16);
    signal byte_i : std_logic_vector(7 downto 0);
begin
    process(
        byte_index, sequence, timestamp_latched,
        ads_ch0_latched, ads_ch1_latched, tmp_latched,
        adxl_x_latched, adxl_y_latched, adxl_z_latched,
        flags_latched, crc_reg
    )
    begin
        byte_i <= x"00";
        case byte_index is
            when 0 => byte_i <= x"A5";
            when 1 => byte_i <= x"5A";
            when 2 => byte_i <= x"01";
            when 3 => byte_i <= x"32";
            when 4 => byte_i <= std_logic_vector(sequence(7 downto 0));
            when 5 => byte_i <= std_logic_vector(sequence(15 downto 8));
            when 6 => byte_i <= x"10";
            when 7 => byte_i <= x"00";
            when 8 => byte_i <= std_logic_vector(timestamp_latched(7 downto 0));
            when 9 => byte_i <= std_logic_vector(timestamp_latched(15 downto 8));
            when 10 => byte_i <= std_logic_vector(timestamp_latched(23 downto 16));
            when 11 => byte_i <= std_logic_vector(timestamp_latched(31 downto 24));
            when 12 => byte_i <= std_logic_vector(ads_ch0_latched(7 downto 0));
            when 13 => byte_i <= std_logic_vector(ads_ch0_latched(15 downto 8));
            when 14 => byte_i <= std_logic_vector(ads_ch0_latched(23 downto 16));
            when 15 => byte_i <= std_logic_vector(ads_ch1_latched(7 downto 0));
            when 16 => byte_i <= std_logic_vector(ads_ch1_latched(15 downto 8));
            when 17 => byte_i <= std_logic_vector(ads_ch1_latched(23 downto 16));
            when 18 => byte_i <= std_logic_vector(tmp_latched(7 downto 0));
            when 19 => byte_i <= std_logic_vector(tmp_latched(15 downto 8));
            when 20 => byte_i <= std_logic_vector(adxl_x_latched(7 downto 0));
            when 21 => byte_i <= std_logic_vector(adxl_x_latched(15 downto 8));
            when 22 => byte_i <= std_logic_vector(adxl_y_latched(7 downto 0));
            when 23 => byte_i <= std_logic_vector(adxl_y_latched(15 downto 8));
            when 24 => byte_i <= std_logic_vector(adxl_z_latched(7 downto 0));
            when 25 => byte_i <= std_logic_vector(adxl_z_latched(15 downto 8));
            when 26 => byte_i <= std_logic_vector(flags_latched(7 downto 0));
            when 27 => byte_i <= std_logic_vector(flags_latched(15 downto 8));
            when 28 => byte_i <= std_logic_vector(crc_reg(7 downto 0));
            when 29 => byte_i <= std_logic_vector(crc_reg(15 downto 8));
            when others => byte_i <= x"00";
        end case;
    end process;

    process(clk)
    begin
        if rising_edge(clk) then
            sample_dropped <= '0';
            if rst = '1' then
                busy <= '0';
                byte_index <= 0;
                sequence <= (others => '0');
                timestamp_latched <= (others => '0');
                ads_ch0_latched <= (others => '0');
                ads_ch1_latched <= (others => '0');
                tmp_latched <= (others => '0');
                adxl_x_latched <= (others => '0');
                adxl_y_latched <= (others => '0');
                adxl_z_latched <= (others => '0');
                flags_latched <= (others => '0');
                crc_reg <= to_unsigned(16#FFFF#, 16);
            else
                if sample_trigger = '1' then
                    if busy = '0' then
                        busy <= '1';
                        byte_index <= 0;
                        timestamp_latched <= timestamp_ms;
                        ads_ch0_latched <= ads_ch0_raw;
                        ads_ch1_latched <= ads_ch1_raw;
                        tmp_latched <= tmp_deci_c;
                        adxl_x_latched <= adxl_x_milli_g;
                        adxl_y_latched <= adxl_y_milli_g;
                        adxl_z_latched <= adxl_z_milli_g;
                        flags_latched <= diagnostic_flags;
                        crc_reg <= to_unsigned(16#FFFF#, 16);
                    else
                        sample_dropped <= '1';
                    end if;
                end if;

                if busy = '1' and tx_ready = '1' then
                    if byte_index >= 2 and byte_index <= 27 then
                        crc_reg <= crc16_next(crc_reg, byte_i);
                    end if;
                    if byte_index = FRAME_LAST_INDEX then
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
