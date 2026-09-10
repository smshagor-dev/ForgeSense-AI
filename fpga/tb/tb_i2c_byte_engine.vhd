library ieee;
use ieee.std_logic_1164.all;
use std.env.all;

entity tb_i2c_byte_engine is end entity;

architecture sim of tb_i2c_byte_engine is
    constant CMD_START : std_logic_vector(2 downto 0) := "000";
    constant CMD_STOP : std_logic_vector(2 downto 0) := "001";
    constant CMD_WRITE : std_logic_vector(2 downto 0) := "010";
    constant CMD_READ_ACK : std_logic_vector(2 downto 0) := "011";
    constant CMD_READ_NACK : std_logic_vector(2 downto 0) := "100";

    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal command_valid : std_logic := '0';
    signal command : std_logic_vector(2 downto 0) := CMD_START;
    signal tx_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal scl_bus : std_logic;
    signal sda_bus : std_logic;
    signal ready : std_logic;
    signal busy : std_logic;
    signal done : std_logic;
    signal ack_error : std_logic;
    signal rx_byte : std_logic_vector(7 downto 0);
    signal scl_drive_low : std_logic;
    signal sda_drive_low : std_logic;

    signal slave_ack_active : std_logic := '0';
    signal slave_read_active : std_logic := '0';
    signal slave_read_low : std_logic := '0';
    signal slave_read_data : std_logic_vector(7 downto 0) := x"A5";
begin
    clk <= not clk after 25 ns;

    -- Open-drain bus model with ideal pull-ups and no clock stretching.
    scl_bus <= '0' when scl_drive_low = '1' else '1';
    sda_bus <= '0' when sda_drive_low = '1' or slave_ack_active = '1' or slave_read_low = '1' else '1';

    dut : entity work.i2c_byte_engine
        generic map (
            CLK_FREQ_HZ => 20000000,
            I2C_FREQ_HZ => 1000000
        )
        port map (
            clk => clk,
            rst => rst,
            command_valid => command_valid,
            command => command,
            tx_byte => tx_byte,
            scl_in => scl_bus,
            sda_in => sda_bus,
            ready => ready,
            busy => busy,
            done => done,
            ack_error => ack_error,
            rx_byte => rx_byte,
            scl_drive_low => scl_drive_low,
            sda_drive_low => sda_drive_low
        );

    -- Minimal read responder. Test bytes use a logic-1 final bit so the responder
    -- naturally releases SDA during the master's ACK/NACK clock.
    process
        variable index_v : integer range 0 to 7;
    begin
        slave_read_low <= '0';
        loop
            wait until slave_read_active = '1';
            index_v := 7;
            while slave_read_active = '1' loop
                if slave_read_data(index_v) = '0' then
                    slave_read_low <= '1';
                else
                    slave_read_low <= '0';
                end if;
                wait until falling_edge(scl_bus) or slave_read_active = '0';
                if slave_read_active = '1' and index_v > 0 then
                    index_v := index_v - 1;
                end if;
            end loop;
            slave_read_low <= '0';
        end loop;
    end process;

    process
        procedure issue(
            constant op : in std_logic_vector(2 downto 0);
            constant data_v : in std_logic_vector(7 downto 0) := x"00"
        ) is
        begin
            command <= op;
            tx_byte <= data_v;
            command_valid <= '1';
            wait until rising_edge(clk);
            command_valid <= '0';
            wait until done = '1';
            wait until rising_edge(clk);
        end procedure;
    begin
        wait for 300 ns;
        wait until rising_edge(clk);
        rst <= '0';
        wait until rising_edge(clk);

        assert ready = '1' and busy = '0' and scl_bus = '1' and sda_bus = '1'
            report "I2C engine did not reset to released-bus idle"
            severity error;

        issue(CMD_START);
        assert scl_drive_low = '1' and sda_drive_low = '1'
            report "I2C START did not finish with bus held low for byte transfer"
            severity error;

        -- Simplified slave holds SDA low throughout writes; the controller only
        -- samples SDA on the ninth ACK clock and does not implement arbitration.
        slave_ack_active <= '1';
        issue(CMD_WRITE, x"90");
        slave_ack_active <= '0';
        assert ack_error = '0' report "I2C address write ACK was not accepted" severity error;

        slave_ack_active <= '1';
        issue(CMD_WRITE, x"00");
        slave_ack_active <= '0';
        assert ack_error = '0' report "I2C register-pointer ACK was not accepted" severity error;

        -- Repeated START before switching to the read address.
        issue(CMD_START);
        slave_ack_active <= '1';
        issue(CMD_WRITE, x"91");
        slave_ack_active <= '0';
        assert ack_error = '0' report "I2C read-address ACK was not accepted" severity error;

        slave_read_data <= x"A5";
        slave_read_active <= '1';
        issue(CMD_READ_ACK);
        slave_read_active <= '0';
        wait for 1 ns;
        assert rx_byte = x"A5"
            report "I2C READ_ACK returned incorrect byte"
            severity error;

        slave_read_data <= x"5B";
        slave_read_active <= '1';
        issue(CMD_READ_NACK);
        slave_read_active <= '0';
        wait for 1 ns;
        assert rx_byte = x"5B"
            report "I2C READ_NACK returned incorrect byte"
            severity error;

        issue(CMD_STOP);
        assert ready = '1' and busy = '0'
            report "I2C engine did not return to idle after STOP"
            severity error;
        assert scl_drive_low = '0' and sda_drive_low = '0' and scl_bus = '1' and sda_bus = '1'
            report "I2C STOP did not release both open-drain lines"
            severity error;

        report "tb_i2c_byte_engine PASS" severity note;
        stop;
        wait;
    end process;
end architecture;
