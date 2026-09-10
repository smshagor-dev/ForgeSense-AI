library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tmp117_controller is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        I2C_FREQ_HZ : positive := 400000;
        ADDRESS_7BIT : std_logic_vector(6 downto 0) := "1001000"
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_request : in std_logic;
        scl_in : in std_logic;
        sda_in : in std_logic;
        scl_drive_low : out std_logic;
        sda_drive_low : out std_logic;
        ready : out std_logic;
        device_ok : out std_logic;
        transport_error : out std_logic;
        sample_valid : out std_logic;
        temperature_deci_c : out signed(15 downto 0)
    );
end entity;

architecture rtl of tmp117_controller is
    constant CMD_START : std_logic_vector(2 downto 0) := "000";
    constant CMD_STOP : std_logic_vector(2 downto 0) := "001";
    constant CMD_WRITE : std_logic_vector(2 downto 0) := "010";
    constant CMD_READ_ACK : std_logic_vector(2 downto 0) := "011";
    constant CMD_READ_NACK : std_logic_vector(2 downto 0) := "100";
    constant REG_TEMP_RESULT : std_logic_vector(7 downto 0) := x"00";
    constant REG_DEVICE_ID : std_logic_vector(7 downto 0) := x"0F";
    constant EXPECTED_DEVICE_ID : std_logic_vector(15 downto 0) := x"0117";

    type state_t is (
        IDLE, START_ISSUE, START_WAIT, ADDR_W_ISSUE, ADDR_W_WAIT,
        REG_ISSUE, REG_WAIT, RESTART_ISSUE, RESTART_WAIT,
        ADDR_R_ISSUE, ADDR_R_WAIT, READ_HI_ISSUE, READ_HI_WAIT,
        READ_LO_ISSUE, READ_LO_WAIT, STOP_ISSUE, STOP_WAIT,
        FAIL_STOP_ISSUE, FAIL_STOP_WAIT
    );
    signal state : state_t := IDLE;
    signal target_is_id : std_logic := '1';
    signal probe_pending : std_logic := '1';
    signal device_ok_reg : std_logic := '0';
    signal read_hi : std_logic_vector(7 downto 0) := (others => '0');
    signal read_lo : std_logic_vector(7 downto 0) := (others => '0');
    signal eng_command_valid : std_logic := '0';
    signal eng_command : std_logic_vector(2 downto 0) := (others => '0');
    signal eng_tx_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal eng_ready, eng_done, eng_ack_error : std_logic;
    signal eng_rx_byte : std_logic_vector(7 downto 0);

    function raw_to_deci_c(raw_value : signed(15 downto 0)) return signed is
        variable raw_i, deci_i : integer;
    begin
        raw_i := to_integer(raw_value);
        if raw_i >= 0 then deci_i := (raw_i * 5 + 32) / 64;
        else deci_i := (raw_i * 5 - 32) / 64; end if;
        return to_signed(deci_i, 16);
    end function;

    function address_byte(read_not_write : std_logic) return std_logic_vector is
    begin
        return ADDRESS_7BIT & read_not_write;
    end function;
begin
    bus_engine : entity work.i2c_byte_engine
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, I2C_FREQ_HZ => I2C_FREQ_HZ)
        port map (
            clk => clk, rst => rst, command_valid => eng_command_valid,
            command => eng_command, tx_byte => eng_tx_byte, scl_in => scl_in,
            sda_in => sda_in, ready => eng_ready, busy => open, done => eng_done,
            ack_error => eng_ack_error, rx_byte => eng_rx_byte,
            scl_drive_low => scl_drive_low, sda_drive_low => sda_drive_low
        );

    process(clk)
        variable completed_word : std_logic_vector(15 downto 0);
    begin
        if rising_edge(clk) then
            eng_command_valid <= '0'; transport_error <= '0'; sample_valid <= '0';
            if rst = '1' then
                state <= IDLE; target_is_id <= '1'; probe_pending <= '1';
                device_ok_reg <= '0'; read_hi <= (others => '0'); read_lo <= (others => '0');
                temperature_deci_c <= (others => '0');
            else
                case state is
                    when IDLE =>
                        if probe_pending = '1' then
                            target_is_id <= '1'; probe_pending <= '0'; state <= START_ISSUE;
                        elsif sample_request = '1' then
                            if device_ok_reg = '1' then target_is_id <= '0'; else target_is_id <= '1'; end if;
                            state <= START_ISSUE;
                        end if;
                    when START_ISSUE =>
                        if eng_ready = '1' then eng_command <= CMD_START; eng_command_valid <= '1'; state <= START_WAIT; end if;
                    when START_WAIT => if eng_done = '1' then state <= ADDR_W_ISSUE; end if;
                    when ADDR_W_ISSUE =>
                        if eng_ready = '1' then eng_command <= CMD_WRITE; eng_tx_byte <= address_byte('0'); eng_command_valid <= '1'; state <= ADDR_W_WAIT; end if;
                    when ADDR_W_WAIT =>
                        if eng_done = '1' then
                            if eng_ack_error = '1' then device_ok_reg <= '0'; transport_error <= '1'; state <= FAIL_STOP_ISSUE;
                            else state <= REG_ISSUE; end if;
                        end if;
                    when REG_ISSUE =>
                        if eng_ready = '1' then
                            eng_command <= CMD_WRITE;
                            if target_is_id = '1' then eng_tx_byte <= REG_DEVICE_ID; else eng_tx_byte <= REG_TEMP_RESULT; end if;
                            eng_command_valid <= '1'; state <= REG_WAIT;
                        end if;
                    when REG_WAIT =>
                        if eng_done = '1' then
                            if eng_ack_error = '1' then device_ok_reg <= '0'; transport_error <= '1'; state <= FAIL_STOP_ISSUE;
                            else state <= RESTART_ISSUE; end if;
                        end if;
                    when RESTART_ISSUE => if eng_ready = '1' then eng_command <= CMD_START; eng_command_valid <= '1'; state <= RESTART_WAIT; end if;
                    when RESTART_WAIT => if eng_done = '1' then state <= ADDR_R_ISSUE; end if;
                    when ADDR_R_ISSUE => if eng_ready = '1' then eng_command <= CMD_WRITE; eng_tx_byte <= address_byte('1'); eng_command_valid <= '1'; state <= ADDR_R_WAIT; end if;
                    when ADDR_R_WAIT =>
                        if eng_done = '1' then
                            if eng_ack_error = '1' then device_ok_reg <= '0'; transport_error <= '1'; state <= FAIL_STOP_ISSUE;
                            else state <= READ_HI_ISSUE; end if;
                        end if;
                    when READ_HI_ISSUE => if eng_ready = '1' then eng_command <= CMD_READ_ACK; eng_command_valid <= '1'; state <= READ_HI_WAIT; end if;
                    when READ_HI_WAIT => if eng_done = '1' then read_hi <= eng_rx_byte; state <= READ_LO_ISSUE; end if;
                    when READ_LO_ISSUE => if eng_ready = '1' then eng_command <= CMD_READ_NACK; eng_command_valid <= '1'; state <= READ_LO_WAIT; end if;
                    when READ_LO_WAIT => if eng_done = '1' then read_lo <= eng_rx_byte; state <= STOP_ISSUE; end if;
                    when STOP_ISSUE => if eng_ready = '1' then eng_command <= CMD_STOP; eng_command_valid <= '1'; state <= STOP_WAIT; end if;
                    when STOP_WAIT =>
                        if eng_done = '1' then
                            completed_word := read_hi & read_lo;
                            if target_is_id = '1' then
                                if completed_word = EXPECTED_DEVICE_ID then device_ok_reg <= '1';
                                else device_ok_reg <= '0'; transport_error <= '1'; end if;
                            else
                                temperature_deci_c <= raw_to_deci_c(signed(completed_word)); sample_valid <= '1';
                            end if;
                            state <= IDLE;
                        end if;
                    when FAIL_STOP_ISSUE => if eng_ready = '1' then eng_command <= CMD_STOP; eng_command_valid <= '1'; state <= FAIL_STOP_WAIT; end if;
                    when FAIL_STOP_WAIT => if eng_done = '1' then state <= IDLE; end if;
                end case;
            end if;
        end if;
    end process;
    ready <= '1' when state = IDLE and probe_pending = '0' else '0';
    device_ok <= device_ok_reg;
end architecture;
