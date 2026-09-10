library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity safety_core is
    generic (WATCHDOG_TIMEOUT_CYCLES : positive := 1000);
    port (
        clk : in std_logic;
        rst : in std_logic;
        startup_done : in std_logic;
        emergency : in std_logic;
        external_hard_trip : in std_logic := '0';
        sensors_valid : in std_logic;
        temperature_deci_c : in unsigned(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        intelligence_kick : in std_logic;
        intelligence_valid : in std_logic;
        intelligence_warning : in std_logic;
        intelligence_critical : in std_logic;
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        hard_warning_status : out std_logic;
        hard_critical_status : out std_logic;
        comm_timeout_status : out std_logic
    );
end entity;

architecture rtl of safety_core is
    signal hard_warning_i : std_logic;
    signal hard_critical_limits_i : std_logic;
    signal hard_critical_i : std_logic;
    signal comm_timeout_i : std_logic;
    signal watchdog_rst_i : std_logic;
begin
    limits : entity work.hard_limit_monitor
        port map (
            temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            sensors_valid => sensors_valid,
            hard_warning => hard_warning_i,
            hard_critical => hard_critical_limits_i
        );

    -- Independent physical comparators/interlocks join the same deterministic
    -- hard-critical path as normalized FPGA limits. This signal is not sourced
    -- by the edge processor or monitoring software.
    hard_critical_i <= hard_critical_limits_i or external_hard_trip;

    watchdog_rst_i <= rst or not startup_done;

    comm_watchdog : entity work.watchdog
        generic map (TIMEOUT_CYCLES => WATCHDOG_TIMEOUT_CYCLES)
        port map (
            clk => clk,
            rst => watchdog_rst_i,
            kick => intelligence_kick,
            expired => comm_timeout_i
        );

    controller : entity work.safety_fsm
        port map (
            clk => clk,
            rst => rst,
            startup_done => startup_done,
            emergency => emergency,
            hard_warning => hard_warning_i,
            hard_critical => hard_critical_i,
            comm_timeout => comm_timeout_i,
            ml_valid => intelligence_valid,
            ml_warning => intelligence_warning,
            ml_critical => intelligence_critical,
            recovery_req => recovery_req,
            state_code => state_code,
            load_enable => load_enable,
            warning_active => warning_active,
            fault_latched => fault_latched
        );

    hard_warning_status <= hard_warning_i;
    hard_critical_status <= hard_critical_i;
    comm_timeout_status <= comm_timeout_i;
end architecture;
