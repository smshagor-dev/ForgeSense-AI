library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_core is
    generic (
        WATCHDOG_TIMEOUT_CYCLES : positive := 1000;
        EXPECTED_MODEL_ID : natural := 1;
        EXPECTED_MODEL_VERSION : natural := 1;
        EXPECTED_FEATURE_SCHEMA : natural := 1;
        MAX_INFERENCE_AGE_MS : natural := 1500
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        startup_done : in std_logic;
        rx_valid : in std_logic;
        rx_byte : in std_logic_vector(7 downto 0);
        emergency : in std_logic;
        sensors_valid : in std_logic;
        temperature_deci_c : in unsigned(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        link_frame_accepted : out std_logic;
        link_frame_rejected : out std_logic
    );
end entity;

architecture rtl of forgesense_core is
    signal frame_valid_i : std_logic;
    signal frame_rejected_i : std_logic;
    signal frame_valid_d : std_logic := '0';
    signal observation_valid_i : std_logic;
    signal sequence_i : unsigned(15 downto 0);
    signal timestamp_i : unsigned(31 downto 0);
    signal model_id_i : unsigned(15 downto 0);
    signal model_version_i : unsigned(15 downto 0);
    signal schema_i : unsigned(15 downto 0);
    signal anomaly_i : unsigned(15 downto 0);
    signal health_i : unsigned(7 downto 0);
    signal confidence_i : unsigned(7 downto 0);
    signal age_i : unsigned(15 downto 0);
    signal intelligence_accepted_i : std_logic;
    signal watchdog_kick_i : std_logic;

    signal ml_have_i : std_logic := '0';
    signal ml_warning_latched_i : std_logic := '0';
    signal ml_critical_latched_i : std_logic := '0';
begin
    receiver : entity work.link_receiver
        port map (
            clk => clk,
            rst => rst,
            rx_valid => rx_valid,
            rx_byte => rx_byte,
            frame_valid => frame_valid_i,
            frame_rejected => frame_rejected_i,
            sequence_number => sequence_i,
            timestamp_ms => timestamp_i,
            model_id => model_id_i,
            model_version => model_version_i,
            feature_schema_version => schema_i,
            observation_valid_flag => observation_valid_i,
            anomaly_q15 => anomaly_i,
            health_class => health_i,
            confidence_q8 => confidence_i,
            inference_age_ms => age_i
        );

    gate : entity work.intelligence_gate
        generic map (
            EXPECTED_MODEL_ID => EXPECTED_MODEL_ID,
            EXPECTED_MODEL_VERSION => EXPECTED_MODEL_VERSION,
            EXPECTED_FEATURE_SCHEMA => EXPECTED_FEATURE_SCHEMA,
            MAX_INFERENCE_AGE_MS => MAX_INFERENCE_AGE_MS
        )
        port map (
            clk => clk,
            rst => rst,
            frame_valid => frame_valid_i,
            observation_valid_flag => observation_valid_i,
            sequence_number => sequence_i,
            model_id => model_id_i,
            model_version => model_version_i,
            feature_schema_version => schema_i,
            inference_age_ms => age_i,
            accepted => intelligence_accepted_i,
            watchdog_kick => watchdog_kick_i
        );

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                ml_have_i <= '0';
                ml_warning_latched_i <= '0';
                ml_critical_latched_i <= '0';
            elsif intelligence_accepted_i = '1' then
                ml_have_i <= '1';
                if health_i = to_unsigned(1, 8) then
                    ml_warning_latched_i <= '1';
                    ml_critical_latched_i <= '0';
                elsif health_i = to_unsigned(2, 8) then
                    ml_warning_latched_i <= '0';
                    ml_critical_latched_i <= '1';
                else
                    ml_warning_latched_i <= '0';
                    ml_critical_latched_i <= '0';
                end if;
            end if;
        end if;
    end process;

    safety : entity work.safety_core
        generic map (
            WATCHDOG_TIMEOUT_CYCLES => WATCHDOG_TIMEOUT_CYCLES
        )
        port map (
            clk => clk,
            rst => rst,
            startup_done => startup_done,
            emergency => emergency,
            sensors_valid => sensors_valid,
            temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            intelligence_kick => watchdog_kick_i,
            intelligence_valid => ml_have_i,
            intelligence_warning => ml_warning_latched_i,
            intelligence_critical => ml_critical_latched_i,
            recovery_req => recovery_req,
            state_code => state_code,
            load_enable => load_enable,
            warning_active => warning_active,
            fault_latched => fault_latched
        );

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                frame_valid_d <= '0';
            else
                frame_valid_d <= frame_valid_i;
            end if;
        end if;
    end process;

    link_frame_accepted <= intelligence_accepted_i;
    link_frame_rejected <=
        frame_rejected_i or (frame_valid_d and not intelligence_accepted_i);
end architecture;
