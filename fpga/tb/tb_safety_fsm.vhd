library ieee;
use ieee.std_logic_1164.all;

entity tb_safety_fsm is
end entity;

architecture sim of tb_safety_fsm is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal startup_done : std_logic := '0';
    signal emergency : std_logic := '0';
    signal hard_warning : std_logic := '0';
    signal hard_critical : std_logic := '0';
    signal comm_timeout : std_logic := '0';
    signal ml_valid : std_logic := '0';
    signal ml_warning : std_logic := '0';
    signal ml_critical : std_logic := '0';
    signal recovery_req : std_logic := '0';
    signal state_code : std_logic_vector(2 downto 0);
    signal load_enable : std_logic;
    signal warning_active : std_logic;
    signal fault_latched : std_logic;
begin
    clk <= not clk after 5 ns;

    dut : entity work.safety_fsm
        port map (
            clk, rst, startup_done, emergency, hard_warning, hard_critical,
            comm_timeout, ml_valid, ml_warning, ml_critical, recovery_req,
            state_code, load_enable, warning_active, fault_latched
        );

    stimulus : process
    begin
        wait for 20 ns;
        rst <= '0';
        wait until rising_edge(clk);
        assert load_enable = '0'
            report "startup must be safe"
            severity failure;

        ml_valid <= '1';
        ml_critical <= '1';
        startup_done <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert state_code = "011" and load_enable = '0'
            report "critical first intelligence must never transiently energize load"
            severity failure;

        rst <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        rst <= '0';
        ml_valid <= '0';
        ml_critical <= '0';
        startup_done <= '0';

        wait until rising_edge(clk);
        startup_done <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert state_code = "001" and load_enable = '1'
            report "normal startup did not reach RUN"
            severity failure;

        hard_warning <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert state_code = "010" and warning_active = '1' and load_enable = '1'
            report "hard warning behavior incorrect"
            severity failure;

        hard_warning <= '0';
        ml_valid <= '1';
        ml_critical <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert state_code = "011" and load_enable = '0'
            report "accepted ML critical must request safe shutdown"
            severity failure;

        ml_critical <= '0';
        recovery_req <= '1';
        wait until rising_edge(clk);
        recovery_req <= '0';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert state_code = "000" and load_enable = '0'
            report "recovery must return through startup"
            severity failure;

        startup_done <= '1';
        ml_valid <= '0';
        wait until rising_edge(clk);
        hard_critical <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert state_code = "100" and fault_latched = '1' and load_enable = '0'
            report "hard critical must latch fault"
            severity failure;

        rst <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert load_enable = '0'
            report "reset must never energize load"
            severity failure;

        report "tb_safety_fsm PASS" severity note;
        wait;
    end process;
end architecture;
