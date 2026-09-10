library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_external_hard_trip is end entity;

architecture sim of tb_external_hard_trip is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal external_trip : std_logic := '0';
    signal recovery_req : std_logic := '0';
    signal state_code : std_logic_vector(2 downto 0);
    signal load_enable, warning_active, fault_latched : std_logic;
    signal hwarn, hcrit, timeout : std_logic;
begin
    clk <= not clk after 5 ns;

    dut : entity work.safety_core
        generic map (WATCHDOG_TIMEOUT_CYCLES => 100)
        port map (
            clk => clk, rst => rst, startup_done => '1', emergency => '0',
            external_hard_trip => external_trip, sensors_valid => '1',
            temperature_deci_c => to_unsigned(300,16),
            vibration_milli_g => to_unsigned(100,16),
            current_milli_a => to_unsigned(500,16),
            intelligence_kick => '1', intelligence_valid => '1',
            intelligence_warning => '0', intelligence_critical => '0',
            recovery_req => recovery_req, state_code => state_code,
            load_enable => load_enable, warning_active => warning_active,
            fault_latched => fault_latched,
            hard_warning_status => hwarn, hard_critical_status => hcrit,
            comm_timeout_status => timeout
        );

    process
    begin
        wait for 20 ns; rst <= '0';
        wait for 20 ns;
        assert load_enable = '1' report "expected RUN before external trip" severity error;
        assert hcrit = '0' severity error;

        external_trip <= '1';
        wait for 10 ns; wait for 1 ns;
        assert hcrit = '1' report "external hard trip missing from hard-critical status" severity error;
        assert fault_latched = '1' report "external hard trip did not latch fault" severity error;
        assert load_enable = '0' report "load remained enabled after external hard trip" severity error;

        external_trip <= '0'; recovery_req <= '1';
        wait for 10 ns; wait for 1 ns;
        assert fault_latched = '0' report "fault did not clear under explicit safe recovery" severity error;

        report "tb_external_hard_trip PASS" severity note;
        wait;
    end process;
end architecture;
