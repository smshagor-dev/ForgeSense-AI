library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity adxl355_controller is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        SPI_FREQ_HZ : positive := 2000000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        drdy : in std_logic;
        miso : in std_logic;
        cs_n : out std_logic;
        sclk : out std_logic;
        mosi : out std_logic;
        device_ok : out std_logic;
        init_error : out std_logic;
        sample_valid : out std_logic;
        x_milli_g : out signed(15 downto 0);
        y_milli_g : out signed(15 downto 0);
        z_milli_g : out signed(15 downto 0)
    );
end entity;

architecture rtl of adxl355_controller is
    constant REG_DEVID_AD : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#00#, 7));
    constant REG_DEVID_MST : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#01#, 7));
    constant REG_PARTID : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#02#, 7));
    constant REG_XDATA3 : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#08#, 7));
    constant REG_FILTER : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#28#, 7));
    constant REG_RANGE : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#2C#, 7));
    constant REG_POWER_CTL : std_logic_vector(6 downto 0) := std_logic_vector(to_unsigned(16#2D#, 7));
    constant EXPECT_DEVID_AD : std_logic_vector(7 downto 0) := x"AD";
    constant EXPECT_DEVID_MST : std_logic_vector(7 downto 0) := x"1D";
    constant EXPECT_PARTID : std_logic_vector(7 downto 0) := x"ED";
    constant FILTER_1KHZ : std_logic_vector(7 downto 0) := x"02";
    constant RANGE_8G : std_logic_vector(7 downto 0) := x"03";
    constant POWER_MEASURE : std_logic_vector(7 downto 0) := x"00";

    type op_kind_t is (OP_READ_REG, OP_WRITE_REG, OP_READ_BURST9);
    type state_t is (DISPATCH, ADDR_ISSUE, ADDR_WAIT, DATA_ISSUE, DATA_WAIT, BURST_ISSUE, BURST_WAIT, COMPLETE, FAULT_HOLD);
    type byte_array9_t is array (0 to 8) of std_logic_vector(7 downto 0);
    signal state : state_t := DISPATCH;
    signal op_kind : op_kind_t := OP_READ_REG;
    signal op_addr : std_logic_vector(6 downto 0) := (others => '0');
    signal op_write_data, op_read_data : std_logic_vector(7 downto 0) := (others => '0');
    signal burst_data : byte_array9_t := (others => (others => '0'));
    signal burst_index : natural range 0 to 8 := 0;
    signal init_step : natural range 0 to 9 := 0;
    signal device_ok_reg, init_error_reg : std_logic := '0';
    signal cs_n_reg : std_logic := '1';
    signal drdy_d : std_logic := '0';
    signal spi_start : std_logic := '0';
    signal spi_tx : std_logic_vector(7 downto 0) := (others => '0');
    signal spi_ready, spi_done : std_logic;
    signal spi_rx : std_logic_vector(7 downto 0);

    function read_instruction(address : std_logic_vector(6 downto 0)) return std_logic_vector is
    begin return address & '1'; end function;
    function write_instruction(address : std_logic_vector(6 downto 0)) return std_logic_vector is
    begin return address & '0'; end function;
    function axis_to_milli_g(b2,b1,b0 : std_logic_vector(7 downto 0)) return signed is
        variable packed : signed(23 downto 0);
        variable raw20_i, scaled_i : integer;
    begin
        packed := signed(b2 & b1 & b0);
        raw20_i := to_integer(shift_right(packed, 4));
        if raw20_i >= 0 then scaled_i := (raw20_i * 156 + 5000) / 10000;
        else scaled_i := (raw20_i * 156 - 5000) / 10000; end if;
        return to_signed(scaled_i, 16);
    end function;
begin
    byte_engine : entity work.spi_mode0_byte_engine
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, SPI_FREQ_HZ => SPI_FREQ_HZ)
        port map (clk => clk, rst => rst, start => spi_start, tx_byte => spi_tx,
                  miso => miso, ready => spi_ready, busy => open, done => spi_done,
                  rx_byte => spi_rx, sclk => sclk, mosi => mosi);

    process(clk)
    begin
        if rising_edge(clk) then
            spi_start <= '0'; sample_valid <= '0'; drdy_d <= drdy;
            if rst = '1' then
                state <= DISPATCH; op_kind <= OP_READ_REG; op_addr <= REG_DEVID_AD;
                op_write_data <= (others => '0'); op_read_data <= (others => '0');
                burst_data <= (others => (others => '0')); burst_index <= 0; init_step <= 0;
                device_ok_reg <= '0'; init_error_reg <= '0'; cs_n_reg <= '1'; drdy_d <= '0';
                x_milli_g <= (others => '0'); y_milli_g <= (others => '0'); z_milli_g <= (others => '0');
            else
                case state is
                    when DISPATCH =>
                        cs_n_reg <= '1';
                        if device_ok_reg = '0' then
                            case init_step is
                                when 0 => op_kind <= OP_READ_REG; op_addr <= REG_DEVID_AD;
                                when 1 => op_kind <= OP_READ_REG; op_addr <= REG_DEVID_MST;
                                when 2 => op_kind <= OP_READ_REG; op_addr <= REG_PARTID;
                                when 3 => op_kind <= OP_WRITE_REG; op_addr <= REG_FILTER; op_write_data <= FILTER_1KHZ;
                                when 4 => op_kind <= OP_WRITE_REG; op_addr <= REG_RANGE; op_write_data <= RANGE_8G;
                                when 5 => op_kind <= OP_WRITE_REG; op_addr <= REG_POWER_CTL; op_write_data <= POWER_MEASURE;
                                when 6 => op_kind <= OP_READ_REG; op_addr <= REG_FILTER;
                                when 7 => op_kind <= OP_READ_REG; op_addr <= REG_RANGE;
                                when 8 => op_kind <= OP_READ_REG; op_addr <= REG_POWER_CTL;
                                when others => device_ok_reg <= '1';
                            end case;
                            if init_step <= 8 then cs_n_reg <= '0'; state <= ADDR_ISSUE; end if;
                        elsif drdy = '1' and drdy_d = '0' then
                            op_kind <= OP_READ_BURST9; op_addr <= REG_XDATA3; burst_index <= 0;
                            cs_n_reg <= '0'; state <= ADDR_ISSUE;
                        end if;
                    when ADDR_ISSUE =>
                        if spi_ready = '1' then
                            if op_kind = OP_WRITE_REG then spi_tx <= write_instruction(op_addr); else spi_tx <= read_instruction(op_addr); end if;
                            spi_start <= '1'; state <= ADDR_WAIT;
                        end if;
                    when ADDR_WAIT =>
                        if spi_done = '1' then
                            if op_kind = OP_READ_BURST9 then burst_index <= 0; state <= BURST_ISSUE; else state <= DATA_ISSUE; end if;
                        end if;
                    when DATA_ISSUE =>
                        if spi_ready = '1' then
                            if op_kind = OP_WRITE_REG then spi_tx <= op_write_data; else spi_tx <= x"00"; end if;
                            spi_start <= '1'; state <= DATA_WAIT;
                        end if;
                    when DATA_WAIT =>
                        if spi_done = '1' then
                            if op_kind = OP_READ_REG then op_read_data <= spi_rx; end if;
                            cs_n_reg <= '1'; state <= COMPLETE;
                        end if;
                    when BURST_ISSUE =>
                        if spi_ready = '1' then spi_tx <= x"00"; spi_start <= '1'; state <= BURST_WAIT; end if;
                    when BURST_WAIT =>
                        if spi_done = '1' then
                            burst_data(burst_index) <= spi_rx;
                            if burst_index = 8 then cs_n_reg <= '1'; state <= COMPLETE;
                            else burst_index <= burst_index + 1; state <= BURST_ISSUE; end if;
                        end if;
                    when COMPLETE =>
                        if device_ok_reg = '0' then
                            case init_step is
                                when 0 => if op_read_data /= EXPECT_DEVID_AD then init_error_reg <= '1'; state <= FAULT_HOLD; else init_step <= 1; state <= DISPATCH; end if;
                                when 1 => if op_read_data /= EXPECT_DEVID_MST then init_error_reg <= '1'; state <= FAULT_HOLD; else init_step <= 2; state <= DISPATCH; end if;
                                when 2 => if op_read_data /= EXPECT_PARTID then init_error_reg <= '1'; state <= FAULT_HOLD; else init_step <= 3; state <= DISPATCH; end if;
                                when 3 | 4 | 5 => init_step <= init_step + 1; state <= DISPATCH;
                                when 6 => if op_read_data /= FILTER_1KHZ then init_error_reg <= '1'; state <= FAULT_HOLD; else init_step <= 7; state <= DISPATCH; end if;
                                when 7 => if (op_read_data and x"03") /= RANGE_8G then init_error_reg <= '1'; state <= FAULT_HOLD; else init_step <= 8; state <= DISPATCH; end if;
                                when 8 => if op_read_data(0) /= '0' then init_error_reg <= '1'; state <= FAULT_HOLD; else init_step <= 9; state <= DISPATCH; end if;
                                when others => state <= DISPATCH;
                            end case;
                        else
                            x_milli_g <= axis_to_milli_g(burst_data(0), burst_data(1), burst_data(2));
                            y_milli_g <= axis_to_milli_g(burst_data(3), burst_data(4), burst_data(5));
                            z_milli_g <= axis_to_milli_g(burst_data(6), burst_data(7), burst_data(8));
                            sample_valid <= '1'; state <= DISPATCH;
                        end if;
                    when FAULT_HOLD => cs_n_reg <= '1';
                end case;
            end if;
        end if;
    end process;
    cs_n <= cs_n_reg; device_ok <= device_ok_reg; init_error <= init_error_reg;
end architecture;
