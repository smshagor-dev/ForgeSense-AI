library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity ads131m02_controller is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        SPI_FREQ_HZ : positive := 2000000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        drdy_n : in std_logic;
        dout : in std_logic;
        cs_n : out std_logic;
        sclk : out std_logic;
        din : out std_logic;
        device_ok : out std_logic;
        frame_error : out std_logic;
        sample_valid : out std_logic;
        status_word : out std_logic_vector(15 downto 0);
        channel0_raw : out signed(23 downto 0);
        channel1_raw : out signed(23 downto 0)
    );
end entity;

architecture rtl of ads131m02_controller is
    constant RREG_ID : std_logic_vector(15 downto 0) := x"A000";
    constant WREG_CLOCK : std_logic_vector(15 downto 0) := x"6180";
    constant RREG_CLOCK : std_logic_vector(15 downto 0) := x"A180";
    constant CLOCK_1KSPS_HR : std_logic_vector(15 downto 0) := x"0316";
    type frame_kind_t is (FRAME_ID_COMMAND, FRAME_ID_RESPONSE, FRAME_CLOCK_WRITE, FRAME_CLOCK_READ_COMMAND, FRAME_CLOCK_READ_RESPONSE, FRAME_SAMPLE);
    type state_t is (WAIT_TRIGGER, BYTE_ISSUE, BYTE_WAIT, FRAME_COMPLETE, FAULT_HOLD);
    type byte_array12_t is array (0 to 11) of std_logic_vector(7 downto 0);
    signal state : state_t := WAIT_TRIGGER;
    signal frame_kind : frame_kind_t := FRAME_ID_COMMAND;
    signal frame_bytes : byte_array12_t := (others => (others => '0'));
    signal byte_index : natural range 0 to 11 := 0;
    signal startup_step : natural range 0 to 5 := 0;
    signal device_ok_reg : std_logic := '0';
    signal cs_n_reg : std_logic := '1';
    signal drdy_d : std_logic := '1';
    signal spi_start : std_logic := '0';
    signal spi_tx : std_logic_vector(7 downto 0) := (others => '0');
    signal spi_ready, spi_done : std_logic;
    signal spi_rx : std_logic_vector(7 downto 0);

    function tx_for_frame(kind : frame_kind_t; index : natural) return std_logic_vector is
    begin
        case kind is
            when FRAME_ID_COMMAND =>
                case index is when 0 => return RREG_ID(15 downto 8); when 1 => return RREG_ID(7 downto 0); when others => return x"00"; end case;
            when FRAME_CLOCK_WRITE =>
                case index is
                    when 0 => return WREG_CLOCK(15 downto 8); when 1 => return WREG_CLOCK(7 downto 0);
                    when 3 => return CLOCK_1KSPS_HR(15 downto 8); when 4 => return CLOCK_1KSPS_HR(7 downto 0);
                    when others => return x"00";
                end case;
            when FRAME_CLOCK_READ_COMMAND =>
                case index is when 0 => return RREG_CLOCK(15 downto 8); when 1 => return RREG_CLOCK(7 downto 0); when others => return x"00"; end case;
            when others => return x"00";
        end case;
    end function;

    function frame_crc(data : byte_array12_t) return unsigned is
        variable crc : unsigned(15 downto 0) := to_unsigned(16#FFFF#, 16);
    begin
        for i in 0 to 8 loop crc := crc16_next(crc, data(i)); end loop;
        return crc;
    end function;

    function crc_is_valid(data : byte_array12_t) return boolean is
        variable expected, observed : unsigned(15 downto 0);
    begin
        expected := frame_crc(data); observed := unsigned(data(9) & data(10));
        return expected = observed and data(11) = x"00";
    end function;
begin
    byte_engine : entity work.spi_mode1_byte_engine
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SPI_FREQ_HZ => SPI_FREQ_HZ)
        port map (clk => clk, rst => rst, start => spi_start, tx_byte => spi_tx,
                  miso => dout, ready => spi_ready, busy => open, done => spi_done,
                  rx_byte => spi_rx, sclk => sclk, mosi => din);

    process(clk)
        variable id_ok, clock_ok, frame_ok : boolean;
    begin
        if rising_edge(clk) then
            spi_start <= '0'; frame_error <= '0'; sample_valid <= '0'; drdy_d <= drdy_n;
            if rst = '1' then
                state <= WAIT_TRIGGER; frame_kind <= FRAME_ID_COMMAND;
                frame_bytes <= (others => (others => '0')); byte_index <= 0; startup_step <= 0;
                device_ok_reg <= '0'; cs_n_reg <= '1'; drdy_d <= '1';
                status_word <= (others => '0'); channel0_raw <= (others => '0'); channel1_raw <= (others => '0');
            else
                case state is
                    when WAIT_TRIGGER =>
                        cs_n_reg <= '1';
                        if drdy_n = '0' and drdy_d = '1' then
                            if device_ok_reg = '1' then frame_kind <= FRAME_SAMPLE;
                            else
                                case startup_step is
                                    when 0 => frame_kind <= FRAME_ID_COMMAND; when 1 => frame_kind <= FRAME_ID_RESPONSE;
                                    when 2 => frame_kind <= FRAME_CLOCK_WRITE; when 3 => frame_kind <= FRAME_CLOCK_READ_COMMAND;
                                    when 4 => frame_kind <= FRAME_CLOCK_READ_RESPONSE; when others => frame_kind <= FRAME_SAMPLE;
                                end case;
                            end if;
                            byte_index <= 0; cs_n_reg <= '0'; state <= BYTE_ISSUE;
                        end if;
                    when BYTE_ISSUE =>
                        if spi_ready = '1' then spi_tx <= tx_for_frame(frame_kind, byte_index); spi_start <= '1'; state <= BYTE_WAIT; end if;
                    when BYTE_WAIT =>
                        if spi_done = '1' then
                            frame_bytes(byte_index) <= spi_rx;
                            if byte_index = 11 then cs_n_reg <= '1'; state <= FRAME_COMPLETE;
                            else byte_index <= byte_index + 1; state <= BYTE_ISSUE; end if;
                        end if;
                    when FRAME_COMPLETE =>
                        case frame_kind is
                            when FRAME_ID_COMMAND => startup_step <= 1; state <= WAIT_TRIGGER;
                            when FRAME_ID_RESPONSE =>
                                id_ok := crc_is_valid(frame_bytes) and frame_bytes(0) = x"22" and frame_bytes(2) = x"00";
                                if id_ok then startup_step <= 2; state <= WAIT_TRIGGER;
                                else frame_error <= '1'; state <= FAULT_HOLD; end if;
                            when FRAME_CLOCK_WRITE => startup_step <= 3; state <= WAIT_TRIGGER;
                            when FRAME_CLOCK_READ_COMMAND => startup_step <= 4; state <= WAIT_TRIGGER;
                            when FRAME_CLOCK_READ_RESPONSE =>
                                clock_ok := crc_is_valid(frame_bytes) and frame_bytes(0) = CLOCK_1KSPS_HR(15 downto 8) and frame_bytes(1) = CLOCK_1KSPS_HR(7 downto 0) and frame_bytes(2) = x"00";
                                if clock_ok then startup_step <= 5; device_ok_reg <= '1'; state <= WAIT_TRIGGER;
                                else frame_error <= '1'; state <= FAULT_HOLD; end if;
                            when FRAME_SAMPLE =>
                                -- The response word is STATUS after a NULL command. WLENGTH lives
                                -- in MODE and must not be inferred from STATUS low bits. A normal
                                -- sample is accepted only when the mandatory output CRC validates.
                                frame_ok := crc_is_valid(frame_bytes);
                                if frame_ok then
                                    status_word <= frame_bytes(0) & frame_bytes(1);
                                    channel0_raw <= signed(frame_bytes(3) & frame_bytes(4) & frame_bytes(5));
                                    channel1_raw <= signed(frame_bytes(6) & frame_bytes(7) & frame_bytes(8));
                                    sample_valid <= '1';
                                else frame_error <= '1'; end if;
                                state <= WAIT_TRIGGER;
                        end case;
                    when FAULT_HOLD => cs_n_reg <= '1';
                end case;
            end if;
        end if;
    end process;
    cs_n <= cs_n_reg; device_ok <= device_ok_reg;
end architecture;
