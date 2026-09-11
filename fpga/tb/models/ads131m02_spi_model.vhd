library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity ads131m02_spi_model is
    port (
        cs_n : in std_logic;
        sclk : in std_logic;
        din : in std_logic;
        dout : out std_logic;
        force_bad_id : in std_logic := '0';
        force_bad_crc : in std_logic := '0';
        force_bad_clock : in std_logic := '0';
        channel0_raw : in signed(23 downto 0) := to_signed(16#100000#, 24);
        channel1_raw : in signed(23 downto 0) := to_signed(-16#080000#, 24)
    );
end entity;

architecture behavioral of ads131m02_spi_model is
    type response_t is (RESP_ZERO, RESP_ID, RESP_CLOCK, RESP_SAMPLE);
    type byte_array12_t is array (0 to 11) of std_logic_vector(7 downto 0);
    signal dout_reg : std_logic := '0';
    signal response_kind : response_t := RESP_ZERO;
    signal clock_register : std_logic_vector(15 downto 0) := x"0000";

    function build_frame(
        kind : response_t;
        bad_id : std_logic;
        bad_crc : std_logic;
        bad_clock : std_logic;
        clock_value : std_logic_vector(15 downto 0);
        ch0 : signed(23 downto 0);
        ch1 : signed(23 downto 0)
    ) return byte_array12_t is
        variable data : byte_array12_t := (others => (others => '0'));
        variable crc : unsigned(15 downto 0) := to_unsigned(16#FFFF#, 16);
    begin
        case kind is
            when RESP_ID =>
                if bad_id = '1' then data(0) := x"00"; else data(0) := x"22"; end if;
                data(1) := x"00";
                data(2) := x"00";
            when RESP_CLOCK =>
                if bad_clock = '1' then
                    data(0) := x"00";
                    data(1) := x"00";
                else
                    data(0) := clock_value(15 downto 8);
                    data(1) := clock_value(7 downto 0);
                end if;
                data(2) := x"00";
            when RESP_SAMPLE =>
                data(0) := x"05";
                data(1) := x"A0";
                data(2) := x"00";
                data(3) := std_logic_vector(ch0(23 downto 16));
                data(4) := std_logic_vector(ch0(15 downto 8));
                data(5) := std_logic_vector(ch0(7 downto 0));
                data(6) := std_logic_vector(ch1(23 downto 16));
                data(7) := std_logic_vector(ch1(15 downto 8));
                data(8) := std_logic_vector(ch1(7 downto 0));
            when others => null;
        end case;

        for i in 0 to 8 loop
            crc := crc16_next(crc, data(i));
        end loop;
        if bad_crc = '1' then crc := crc xor to_unsigned(1, 16); end if;
        data(9) := std_logic_vector(crc(15 downto 8));
        data(10) := std_logic_vector(crc(7 downto 0));
        data(11) := x"00";
        return data;
    end function;
begin
    dout <= dout_reg;

    process(cs_n, sclk)
        variable tx_frame : byte_array12_t := (others => (others => '0'));
        variable rx_frame : byte_array12_t := (others => (others => '0'));
        variable rx_shift : std_logic_vector(7 downto 0) := (others => '0');
        variable byte_index : integer range 0 to 11 := 0;
        variable bit_index : integer range 0 to 7 := 7;
        variable completed : std_logic_vector(7 downto 0);
    begin
        if falling_edge(cs_n) then
            tx_frame := build_frame(response_kind, force_bad_id, force_bad_crc, force_bad_clock, clock_register, channel0_raw, channel1_raw);
            rx_frame := (others => (others => '0'));
            rx_shift := (others => '0');
            byte_index := 0;
            bit_index := 7;
            dout_reg <= '0';
        elsif rising_edge(cs_n) then
            if rx_frame(0) = x"A0" and rx_frame(1) = x"00" then
                response_kind <= RESP_ID;
            elsif rx_frame(0) = x"61" and rx_frame(1) = x"80" then
                clock_register <= rx_frame(3) & rx_frame(4);
                response_kind <= RESP_SAMPLE;
            elsif rx_frame(0) = x"A1" and rx_frame(1) = x"80" then
                response_kind <= RESP_CLOCK;
            else
                response_kind <= RESP_SAMPLE;
            end if;
            dout_reg <= '0';
        elsif cs_n = '0' and rising_edge(sclk) then
            -- CPHA=1: device updates DOUT on the leading edge.
            dout_reg <= tx_frame(byte_index)(bit_index);
        elsif cs_n = '0' and falling_edge(sclk) then
            -- Controller samples DOUT and the device samples DIN on the trailing edge.
            rx_shift(bit_index) := din;
            if bit_index = 0 then
                completed := rx_shift;
                rx_frame(byte_index) := completed;
                rx_shift := (others => '0');
                bit_index := 7;
                if byte_index < 11 then byte_index := byte_index + 1; end if;
            else
                bit_index := bit_index - 1;
            end if;
        end if;
    end process;
end architecture;
