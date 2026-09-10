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
        monotonic_ms : in unsigned(31 downto 0);
        temperature_deci_c : in signed(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        temperature_valid : in std_logic;
        vibration_valid : in std_logic;
        current_valid : in std_logic;

        ml_rx_valid : in std_logic;
        ml_rx_byte : in std_logic_vector(7 downto 0);

        sensor_tx_ready : in std_logic;
        sensor_tx_valid : out std_logic;
        sensor_tx_byte : out std_logic_vector(7 downto 0);
        sensor_sample_dropped : out std_logic;

        emergency : in std_logic;
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
begin
    sensors_valid_i <=
        temperature_valid and vibration_valid and current_valid;

    sensor_flags_i(0) <= temperature_valid;
    sensor_flags_i(1) <= vibration_valid;
    sensor_flags_i(2) <= current_valid;
    sensor_flags_i(15 downto 3) <= (others => '0');

    temperature_safety_i <=
        unsigned(temperature_deci_c)
        when temperature_deci_c(15) = '0'
        else (others => '0');

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                ready_latched <= '0';
            elsif accepted_i = '1' then
                ready_latched <= '1';
            end if;
        end if;
    end process;

    sensor_tx : entity work.sensor_link_tx
        port map (
            clk => clk,
            rst => rst,
            sample_trigger => sample_tick,
            timestamp_ms => monotonic_ms,
            temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            sensor_flags => sensor_flags_i,
            tx_ready => sensor_tx_ready,
            tx_valid => sensor_tx_valid,
            tx_byte => sensor_tx_byte,
            sample_dropped => sensor_sample_dropped
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
            clk => clk,
            rst => rst,
            startup_done => ready_latched,
            rx_valid => ml_rx_valid,
            rx_byte => ml_rx_byte,
            emergency => emergency,
            sensors_valid => sensors_valid_i,
            temperature_deci_c => temperature_safety_i,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            recovery_req => recovery_req,
            state_code => state_code,
            load_enable => load_enable,
            warning_active => warning_active,
            fault_latched => fault_latched,
            link_frame_accepted => accepted_i,
            link_frame_rejected => rejected_i
        );

    operational_ready <= ready_latched;
    link_frame_accepted <= accepted_i;
    link_frame_rejected <= rejected_i;
end architecture;
