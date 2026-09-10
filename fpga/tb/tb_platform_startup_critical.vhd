library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_platform_startup_critical is
end entity;

architecture sim of tb_platform_startup_critical is
    type byte_array_t is array (natural range <>) of std_logic_vector(7 downto 0);
    constant CRITICAL_FRAME : byte_array_t(0 to 27) := (
        x"A5", x"5A", x"01", x"10", x"00", x"00", x"0E", x"00",
        x"E8", x"03", x"00", x"00", x"01", x"00", x"01", x"00",
        x"01", x"00", x"01", x"00", x"99", x"79", x"02", x"E6",
        x"00", x"00", x"3D", x"5D"
    );

    signal clk : std_logic := '0';
    signal rst : std_logic := '1';

    signal sample_tick : std_logic := '0';
    signal monotonic_ms : unsigned(31 downto 0) := (others => '0');
    signal temperature_deci_c : signed(15 downto 0) := to_signed(300, 16);
    signal vibration_milli_g : unsigned(15 downto 0) := to_unsigned(120, 16);
    signal current_milli_a : unsigned(15 downto 0) := to_unsigned(1400, 16);

    signal ml_rx_valid : std_logic := '0';
    signal ml_rx_byte : std_logic_vector(7 downto 0) := (others => '0');

    signal sensor_tx_valid : std_logic;
    signal sensor_tx_byte : std_logic_vector(7 downto 0);
    signal sensor_sample_dropped : std_logic;

    signal state_code : std_logic_vector(2 downto 0);
    signal load_enable : std_logic;
    signal warning_active : std_logic;
    signal fault_latched : std_logic;
    signal operational_ready : std_logic;
    signal link_frame_accepted : std_logic;
    signal link_frame_rejected : std_logic;
begin
    clk <= not clk after 5 ns;

    dut : entity work.forgesense_platform_core
        generic map (
            WATCHDOG_TIMEOUT_CYCLES => 100
        )
        port map (
            clk => clk,
            rst => rst,
            sample_tick => sample_tick,
            monotonic_ms => monotonic_ms,
            temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            temperature_valid => '1',
            vibration_valid => '1',
            current_valid => '1',
            ml_rx_valid => ml_rx_valid,
            ml_rx_byte => ml_rx_byte,
            sensor_tx_ready => '1',
            sensor_tx_valid => sensor_tx_valid,
            sensor_tx_byte => sensor_tx_byte,
            sensor_sample_dropped => sensor_sample_dropped,
            emergency => '0',
            recovery_req => '0',
            state_code => state_code,
            load_enable => load_enable,
            warning_active => warning_active,
            fault_latched => fault_latched,
            operational_ready => operational_ready,
            link_frame_accepted => link_frame_accepted,
            link_frame_rejected => link_frame_rejected
        );

    stimulus : process
    begin
        wait for 20 ns;
        wait until rising_edge(clk);
        rst <= '0';

        for index in CRITICAL_FRAME'range loop
            ml_rx_byte <= CRITICAL_FRAME(index);
            ml_rx_valid <= '1';
            wait until rising_edge(clk);
            assert load_enable = '0'
                report "load energized while first critical intelligence frame arrived"
                severity failure;
        end loop;
        ml_rx_valid <= '0';

        for delay in 0 to 7 loop
            wait until rising_edge(clk);
            wait for 1 ns;
            assert load_enable = '0'
                report "load transiently energized during critical startup transition"
                severity failure;
        end loop;

        assert operational_ready = '1'
            report "accepted intelligence did not complete startup handshake"
            severity failure;
        assert state_code = "011"
            report "critical first intelligence did not end in shutdown"
            severity failure;
        assert link_frame_rejected = '0'
            report "valid critical frame was unexpectedly rejected"
            severity failure;

        report "tb_platform_startup_critical PASS" severity note;
        wait;
    end process;
end architecture;
