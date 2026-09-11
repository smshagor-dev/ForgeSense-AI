library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_platform_core is
    generic (
        WATCHDOG_TIMEOUT_CYCLES : positive := 27000000;
        EXPECTED_MODEL_ID : natural := 1;
        EXPECTED_MODEL_VERSION : natural := 1;
        EXPECTED_FEATURE_SCHEMA : natural := 1;
        MAX_INFERENCE_AGE_MS : natural := 1500
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        sample_tick : in std_logic;
        status_tick : in std_logic := '0';
        monotonic_ms : in unsigned(31 downto 0);
        temperature_deci_c : in signed(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        temperature_valid : in std_logic;
        vibration_valid : in std_logic;
        current_valid : in std_logic;
        device_identity_ok : in std_logic := '0';
        device_transport_error : in std_logic := '0';
        device_diagnostics : in std_logic_vector(5 downto 0) := (others => '0');
        ml_rx_valid : in std_logic;
        ml_rx_byte : in std_logic_vector(7 downto 0);
        sensor_tx_ready : in std_logic;
        sensor_tx_valid : out std_logic;
        sensor_tx_byte : out std_logic_vector(7 downto 0);
        sensor_sample_dropped : out std_logic;
        emergency : in std_logic;
        external_hard_trip : in std_logic := '0';
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        operational_ready : out std_logic;
        link_frame_accepted : out std_logic;
        link_frame_rejected : out std_logic
    );
end entity;

architecture rtl of forgesense_platform_core is
    signal sensor_flags_i : unsigned(15 downto 0) := (others => '0');
    signal sensors_valid_i : std_logic;
    signal temperature_safety_i : unsigned(15 downto 0);
    signal accepted_i : std_logic;
    signal rejected_i : std_logic;
    signal ready_latched : std_logic := '0';
    signal state_code_i : std_logic_vector(2 downto 0);
    signal load_enable_i : std_logic;
    signal warning_active_i : std_logic;
    signal fault_latched_i : std_logic;
    signal hard_warning_i : std_logic;
    signal hard_critical_i : std_logic;
    signal comm_timeout_i : std_logic;
    signal ml_warning_i : std_logic;
    signal ml_critical_i : std_logic;
    signal control_flags_i : unsigned(7 downto 0) := (others => '0');
    signal safety_flags_i : unsigned(15 downto 0) := (others => '0');
    signal status_vector_i : std_logic_vector(26 downto 0);
    signal last_status_vector_i : std_logic_vector(26 downto 0) := (others => '0');
    signal status_change_i : std_logic := '0';
    signal status_trigger_i : std_logic;
    signal raw_sensor_valid_i : std_logic;
    signal raw_sensor_byte_i : std_logic_vector(7 downto 0);
    signal raw_sensor_ready_i : std_logic;
    signal raw_status_valid_i : std_logic;
    signal raw_status_byte_i : std_logic_vector(7 downto 0);
    signal raw_status_ready_i : std_logic;
begin
    sensors_valid_i <= temperature_valid and vibration_valid and current_valid;
    sensor_flags_i(0) <= temperature_valid;
    sensor_flags_i(1) <= vibration_valid;
    sensor_flags_i(2) <= current_valid;
    sensor_flags_i(15 downto 3) <= (others => '0');

    temperature_safety_i <= unsigned(temperature_deci_c)
        when temperature_deci_c(15) = '0' else (others => '0');

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then ready_latched <= '0';
            elsif accepted_i = '1' then ready_latched <= '1'; end if;
        end if;
    end process;

    control_flags_i(0) <= load_enable_i;
    control_flags_i(1) <= warning_active_i;
    control_flags_i(2) <= fault_latched_i;
    control_flags_i(3) <= ready_latched;
    control_flags_i(7 downto 4) <= (others => '0');

    safety_flags_i(0) <= hard_warning_i;
    safety_flags_i(1) <= hard_critical_i;
    safety_flags_i(2) <= comm_timeout_i;
    safety_flags_i(3) <= ml_warning_i;
    safety_flags_i(4) <= ml_critical_i;
    safety_flags_i(5) <= emergency;
    safety_flags_i(6) <= sensors_valid_i;
    safety_flags_i(7) <= device_identity_ok;
    safety_flags_i(8) <= device_transport_error;
    -- Per-device commissioning diagnostics. These are read-only observations
    -- and do not add control authority or alter hard-safety decisions.
    safety_flags_i(9) <= device_diagnostics(0);  -- TMP117 trusted/configured
    safety_flags_i(10) <= device_diagnostics(1); -- ADXL355 trusted/configured
    safety_flags_i(11) <= device_diagnostics(2); -- ADS131M02 trusted/configured
    safety_flags_i(12) <= device_diagnostics(3); -- TMP117 transport error
    safety_flags_i(13) <= device_diagnostics(4); -- ADXL355 init/transport error
    safety_flags_i(14) <= device_diagnostics(5); -- ADS131M02 frame/config error
    safety_flags_i(15) <= '0';

    status_vector_i <= state_code_i & std_logic_vector(control_flags_i) & std_logic_vector(safety_flags_i);

    process (clk)
    begin
        if rising_edge(clk) then
            status_change_i <= '0';
            if rst = '1' then last_status_vector_i <= (others => '0');
            elsif status_vector_i /= last_status_vector_i then
                last_status_vector_i <= status_vector_i;
                status_change_i <= '1';
            end if;
        end if;
    end process;

    status_trigger_i <= status_tick or status_change_i;

    sensor_tx : entity work.sensor_link_tx
        port map (
            clk => clk, rst => rst, sample_trigger => sample_tick,
            timestamp_ms => monotonic_ms, temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g, current_milli_a => current_milli_a,
            sensor_flags => sensor_flags_i, tx_ready => raw_sensor_ready_i,
            tx_valid => raw_sensor_valid_i, tx_byte => raw_sensor_byte_i,
            sample_dropped => sensor_sample_dropped
        );

    status_tx : entity work.status_link_tx
        port map (
            clk => clk, rst => rst, status_trigger => status_trigger_i,
            timestamp_ms => monotonic_ms, state_code => state_code_i,
            control_flags => control_flags_i, safety_flags => safety_flags_i,
            tx_ready => raw_status_ready_i, tx_valid => raw_status_valid_i,
            tx_byte => raw_status_byte_i
        );

    tx_arbiter : entity work.link_tx_arbiter
        port map (
            clk => clk, rst => rst,
            status_valid => raw_status_valid_i, status_byte => raw_status_byte_i,
            status_ready => raw_status_ready_i,
            sensor_valid => raw_sensor_valid_i, sensor_byte => raw_sensor_byte_i,
            sensor_ready => raw_sensor_ready_i,
            uart_ready => sensor_tx_ready, uart_valid => sensor_tx_valid,
            uart_byte => sensor_tx_byte
        );

    control : entity work.forgesense_core
        generic map (
            WATCHDOG_TIMEOUT_CYCLES => WATCHDOG_TIMEOUT_CYCLES,
            EXPECTED_MODEL_ID => EXPECTED_MODEL_ID,
            EXPECTED_MODEL_VERSION => EXPECTED_MODEL_VERSION,
            EXPECTED_FEATURE_SCHEMA => EXPECTED_FEATURE_SCHEMA,
            MAX_INFERENCE_AGE_MS => MAX_INFERENCE_AGE_MS
        )
        port map (
            clk => clk, rst => rst, startup_done => ready_latched,
            rx_valid => ml_rx_valid, rx_byte => ml_rx_byte,
            emergency => emergency, external_hard_trip => external_hard_trip,
            sensors_valid => sensors_valid_i,
            temperature_deci_c => temperature_safety_i,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            recovery_req => recovery_req,
            state_code => state_code_i, load_enable => load_enable_i,
            warning_active => warning_active_i, fault_latched => fault_latched_i,
            link_frame_accepted => accepted_i, link_frame_rejected => rejected_i,
            hard_warning_status => hard_warning_i,
            hard_critical_status => hard_critical_i,
            comm_timeout_status => comm_timeout_i,
            ml_warning_status => ml_warning_i,
            ml_critical_status => ml_critical_i
        );

    state_code <= state_code_i;
    load_enable <= load_enable_i;
    warning_active <= warning_active_i;
    fault_latched <= fault_latched_i;
    operational_ready <= ready_latched;
    link_frame_accepted <= accepted_i;
    link_frame_rejected <= rejected_i;
end architecture;
