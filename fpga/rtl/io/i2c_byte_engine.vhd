library ieee;
use ieee.std_logic_1164.all;

entity i2c_byte_engine is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        I2C_FREQ_HZ : positive := 400000
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        command_valid : in std_logic;
        command : in std_logic_vector(2 downto 0);
        tx_byte : in std_logic_vector(7 downto 0);
        scl_in : in std_logic;
        sda_in : in std_logic;
        ready : out std_logic;
        busy : out std_logic;
        done : out std_logic;
        ack_error : out std_logic;
        rx_byte : out std_logic_vector(7 downto 0);
        scl_drive_low : out std_logic;
        sda_drive_low : out std_logic
    );
end entity;

architecture rtl of i2c_byte_engine is
    constant CMD_START : std_logic_vector(2 downto 0) := "000";
    constant CMD_STOP : std_logic_vector(2 downto 0) := "001";
    constant CMD_WRITE : std_logic_vector(2 downto 0) := "010";
    constant CMD_READ_ACK : std_logic_vector(2 downto 0) := "011";
    constant CMD_READ_NACK : std_logic_vector(2 downto 0) := "100";

    function half_period_clks(freq : positive; bus_freq : positive) return positive is
        constant denominator : positive := 2 * bus_freq;
        variable result : natural;
    begin
        result := (freq + denominator - 1) / denominator;
        if result < 1 then return 1; end if;
        return result;
    end function;

    constant HALF_CLKS : positive := half_period_clks(CLK_FREQ_HZ, I2C_FREQ_HZ);
    type state_t is (
        IDLE,
        START_RELEASE, START_SDA_LOW,
        STOP_LOW, STOP_SCL_HIGH, STOP_SDA_HIGH,
        WRITE_LOW, WRITE_HIGH, WRITE_ACK_LOW, WRITE_ACK_HIGH,
        READ_LOW, READ_HIGH, READ_ACK_LOW, READ_ACK_HIGH
    );
    signal state : state_t := IDLE;
    signal count : natural range 0 to HALF_CLKS - 1 := 0;
    signal bit_index : natural range 0 to 7 := 7;
    signal tx_latched : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_shift : std_logic_vector(7 downto 0) := (others => '0');
    signal ack_after_read : std_logic := '0';
    signal scl_low : std_logic := '0';
    signal sda_low : std_logic := '0';
    signal done_reg : std_logic := '0';
    signal ack_error_reg : std_logic := '0';

    function elapsed(c : natural) return boolean is
    begin
        return c = HALF_CLKS - 1;
    end function;
begin
    assert (2 * I2C_FREQ_HZ) <= CLK_FREQ_HZ
        report "I2C_FREQ_HZ requires at least two FPGA clocks per I2C period"
        severity failure;

    process(clk)
    begin
        if rising_edge(clk) then
            done_reg <= '0';
            if rst = '1' then
                state <= IDLE;
                count <= 0;
                bit_index <= 7;
                tx_latched <= (others => '0');
                rx_shift <= (others => '0');
                ack_after_read <= '0';
                scl_low <= '0';
                sda_low <= '0';
                ack_error_reg <= '0';
            else
                case state is
                    when IDLE =>
                        count <= 0;
                        if command_valid = '1' then
                            ack_error_reg <= '0';
                            case command is
                                when CMD_START =>
                                    scl_low <= '0'; sda_low <= '0'; state <= START_RELEASE;
                                when CMD_STOP =>
                                    scl_low <= '1'; sda_low <= '1'; state <= STOP_LOW;
                                when CMD_WRITE =>
                                    tx_latched <= tx_byte; bit_index <= 7; scl_low <= '1';
                                    if tx_byte(7) = '0' then sda_low <= '1'; else sda_low <= '0'; end if;
                                    state <= WRITE_LOW;
                                when CMD_READ_ACK | CMD_READ_NACK =>
                                    bit_index <= 7; rx_shift <= (others => '0');
                                    scl_low <= '1'; sda_low <= '0';
                                    if command = CMD_READ_ACK then ack_after_read <= '1'; else ack_after_read <= '0'; end if;
                                    state <= READ_LOW;
                                when others => null;
                            end case;
                        end if;

                    when START_RELEASE =>
                        if scl_in = '1' and sda_in = '1' then
                            if elapsed(count) then count <= 0; sda_low <= '1'; state <= START_SDA_LOW;
                            else count <= count + 1; end if;
                        else count <= 0; end if;
                    when START_SDA_LOW =>
                        if scl_in = '1' then
                            if elapsed(count) then count <= 0; scl_low <= '1'; done_reg <= '1'; state <= IDLE;
                            else count <= count + 1; end if;
                        else count <= 0; end if;

                    when STOP_LOW =>
                        if elapsed(count) then count <= 0; scl_low <= '0'; state <= STOP_SCL_HIGH;
                        else count <= count + 1; end if;
                    when STOP_SCL_HIGH =>
                        if scl_in = '1' then
                            if elapsed(count) then count <= 0; sda_low <= '0'; state <= STOP_SDA_HIGH;
                            else count <= count + 1; end if;
                        else count <= 0; end if;
                    when STOP_SDA_HIGH =>
                        if scl_in = '1' and sda_in = '1' then
                            if elapsed(count) then count <= 0; done_reg <= '1'; state <= IDLE;
                            else count <= count + 1; end if;
                        else count <= 0; end if;

                    when WRITE_LOW =>
                        if elapsed(count) then count <= 0; scl_low <= '0'; state <= WRITE_HIGH;
                        else count <= count + 1; end if;
                    when WRITE_HIGH =>
                        if scl_in = '1' then
                            if elapsed(count) then
                                count <= 0; scl_low <= '1';
                                if bit_index = 0 then
                                    sda_low <= '0'; state <= WRITE_ACK_LOW;
                                else
                                    bit_index <= bit_index - 1;
                                    if tx_latched(bit_index - 1) = '0' then sda_low <= '1'; else sda_low <= '0'; end if;
                                    state <= WRITE_LOW;
                                end if;
                            else count <= count + 1; end if;
                        else count <= 0; end if;
                    when WRITE_ACK_LOW =>
                        if elapsed(count) then count <= 0; scl_low <= '0'; state <= WRITE_ACK_HIGH;
                        else count <= count + 1; end if;
                    when WRITE_ACK_HIGH =>
                        if scl_in = '1' then
                            if elapsed(count) then
                                count <= 0; ack_error_reg <= sda_in; scl_low <= '1'; sda_low <= '0';
                                done_reg <= '1'; state <= IDLE;
                            else count <= count + 1; end if;
                        else count <= 0; end if;

                    when READ_LOW =>
                        sda_low <= '0';
                        if elapsed(count) then count <= 0; scl_low <= '0'; state <= READ_HIGH;
                        else count <= count + 1; end if;
                    when READ_HIGH =>
                        if scl_in = '1' then
                            if elapsed(count) then
                                count <= 0; rx_shift(bit_index) <= sda_in; scl_low <= '1';
                                if bit_index = 0 then
                                    if ack_after_read = '1' then sda_low <= '1'; else sda_low <= '0'; end if;
                                    state <= READ_ACK_LOW;
                                else
                                    bit_index <= bit_index - 1; state <= READ_LOW;
                                end if;
                            else count <= count + 1; end if;
                        else count <= 0; end if;
                    when READ_ACK_LOW =>
                        if elapsed(count) then count <= 0; scl_low <= '0'; state <= READ_ACK_HIGH;
                        else count <= count + 1; end if;
                    when READ_ACK_HIGH =>
                        if scl_in = '1' then
                            if elapsed(count) then
                                count <= 0; scl_low <= '1'; sda_low <= '0'; done_reg <= '1'; state <= IDLE;
                            else count <= count + 1; end if;
                        else count <= 0; end if;
                end case;
            end if;
        end if;
    end process;

    ready <= '1' when state = IDLE else '0';
    busy <= '0' when state = IDLE else '1';
    done <= done_reg;
    ack_error <= ack_error_reg;
    rx_byte <= rx_shift;
    scl_drive_low <= scl_low;
    sda_drive_low <= sda_low;
end architecture;
