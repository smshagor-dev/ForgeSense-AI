library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_board_core is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        UART_BAUD_RATE : positive := 115200;
        SENSOR_SAMPLE_RATE_HZ : positive := 10;
        WATCHDOG_TIMEOUT_MS : positive := 1500
    );
    port (
        clk : in std_logic;
        rst : in std_logic;

        uart_rx_i : in std_logic;
        uart_tx_o : out std_logic;

        temperature_deci_c : in signed(15 downto 0);
        vibration_milli_g : in unsigned(15 downto 0);
        current_milli_a : in unsigned(15 downto 0);
        temperature_valid : in std_logic;
        vibration_valid : in std_logic;
        current_valid : in std_logic;

        emergency : in std_logic;
        recovery_req : in std_logic;

        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic;
        operational_ready : out std_logic;
        uart_framing_error : out std_logic;
        sensor_sample_dropped : out std_logic
    );
end entity;

architecture rtl of forgesense_board_core is
    function watchdog_cycles(
        freq : positive;
        timeout_ms : positive
    ) return positive is
        variable result : positive;
    begin
        result := (freq / 1000) * timeout_ms;
        return result;
    end function;

    constant WATCHDOG_CYCLES : positive :=
        watchdog_cycles(CLK_FREQ_HZ, WATCHDOG_TIMEOUT_MS);

    signal sample_tick_i : std_logic;
    signal monotonic_ms_i : unsigned(31 downto 0);

    signal rx_valid_i : std_logic;
    signal rx_byte_i : std_logic_vector(7 downto 0);
    signal tx_ready_i : std_logic;
    signal tx_valid_i : std_logic;
    signal tx_byte_i : std_logic_vector(7 downto 0);

    signal accepted_i : std_logic;
    signal rejected_i : std_logic;
begin
    sample_clock : entity work.sample_scheduler
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ,
            SAMPLE_RATE_HZ => SENSOR_SAMPLE_RATE_HZ
        )
        port map (
            clk => clk,
            rst => rst,
            sample_tick => sample_tick_i
        );

    timebase : entity work.timebase_ms
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ
        )
        port map (
            clk => clk,
            rst => rst,
            monotonic_ms => monotonic_ms_i
        );

    serial_rx : entity work.uart_rx
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ,
            BAUD_RATE => UART_BAUD_RATE
        )
        port map (
            clk => clk,
            rst => rst,
            rx_serial => uart_rx_i,
            data_valid => rx_valid_i,
            data_byte => rx_byte_i,
            framing_error => uart_framing_error
        );

    serial_tx : entity work.uart_tx
        generic map (
            CLK_FREQ_HZ => CLK_FREQ_HZ,
            BAUD_RATE => UART_BAUD_RATE
        )
        port map (
            clk => clk,
            rst => rst,
            data_valid => tx_valid_i,
            data_byte => tx_byte_i,
            ready => tx_ready_i,
            tx_serial => uart_tx_o
        );

    platform : entity work.forgesense_platform_core
        generic map (
            WATCHDOG_TIMEOUT_CYCLES => WATCHDOG_CYCLES
        )
        port map (
            clk => clk,
            rst => rst,
            sample_tick => sample_tick_i,
            monotonic_ms => monotonic_ms_i,
            temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            temperature_valid => temperature_valid,
            vibration_valid => vibration_valid,
            current_valid => current_valid,
            ml_rx_valid => rx_valid_i,
            ml_rx_byte => rx_byte_i,
            sensor_tx_ready => tx_ready_i,
            sensor_tx_valid => tx_valid_i,
            sensor_tx_byte => tx_byte_i,
            sensor_sample_dropped => sensor_sample_dropped,
            emergency => emergency,
            recovery_req => recovery_req,
            state_code => state_code,
            load_enable => load_enable,
            warning_active => warning_active,
            fault_latched => fault_latched,
            operational_ready => operational_ready,
            link_frame_accepted => accepted_i,
            link_frame_rejected => rejected_i
        );
end architecture;
