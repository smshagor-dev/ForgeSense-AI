library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity forgesense_tang_nano_9k_smoke_top is
    generic (
        CLK_FREQ_HZ : positive := 27000000;
        UART_BAUD_RATE : positive := 115200
    );
    port (
        clk_27m_i : in std_logic;
        reset_n_i : in std_logic;
        esp32_uart_rx_i : in std_logic;
        esp32_uart_tx_o : out std_logic;
        tmp_scl_io : inout std_logic;
        tmp_sda_io : inout std_logic;
        adxl_drdy_i : in std_logic;
        adxl_miso_i : in std_logic;
        adxl_cs_n_o : out std_logic;
        adxl_sclk_o : out std_logic;
        adxl_mosi_o : out std_logic;
        ads_drdy_n_i : in std_logic;
        ads_dout_i : in std_logic;
        ads_cs_n_o : out std_logic;
        ads_sclk_o : out std_logic;
        ads_din_o : out std_logic;
        analog_hard_trip_i : in std_logic;
        estop_sense_i : in std_logic;
        recovery_req_i : in std_logic;
        load_enable_o : out std_logic
    );
end entity;

architecture rtl of forgesense_tang_nano_9k_smoke_top is
    signal reset_pipe : std_logic_vector(2 downto 0) := (others => '1');
    signal rst_i : std_logic;
    signal rx_valid_i : std_logic;
    signal rx_byte_i : std_logic_vector(7 downto 0);
    signal tx_ready_i : std_logic;
    signal tx_valid_i : std_logic := '0';
    signal tx_byte_i : std_logic_vector(7 downto 0) := (others => '0');
    signal pending_i : std_logic := '0';
    signal pending_byte_i : std_logic_vector(7 downto 0) := (others => '0');
    signal heartbeat_counter_i : natural range 0 to CLK_FREQ_HZ - 1 := 0;
begin
    process(clk_27m_i)
    begin
        if rising_edge(clk_27m_i) then
            if reset_n_i = '0' then
                reset_pipe <= (others => '1');
            else
                reset_pipe <= reset_pipe(1 downto 0) & '0';
            end if;
        end if;
    end process;
    rst_i <= reset_pipe(2);

    serial_rx : entity work.uart_rx
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, BAUD_RATE => UART_BAUD_RATE)
        port map (
            clk => clk_27m_i,
            rst => rst_i,
            rx_serial => esp32_uart_rx_i,
            data_valid => rx_valid_i,
            data_byte => rx_byte_i,
            framing_error => open
        );

    serial_tx : entity work.uart_tx
        generic map (CLK_FREQ_HZ => CLK_FREQ_HZ, BAUD_RATE => UART_BAUD_RATE)
        port map (
            clk => clk_27m_i,
            rst => rst_i,
            data_valid => tx_valid_i,
            data_byte => tx_byte_i,
            ready => tx_ready_i,
            tx_serial => esp32_uart_tx_o
        );

    process(clk_27m_i)
    begin
        if rising_edge(clk_27m_i) then
            if rst_i = '1' then
                tx_valid_i <= '0';
                tx_byte_i <= (others => '0');
                pending_i <= '0';
                pending_byte_i <= (others => '0');
                heartbeat_counter_i <= 0;
            else
                tx_valid_i <= '0';

                if pending_i = '1' and tx_ready_i = '1' then
                    tx_byte_i <= pending_byte_i;
                    tx_valid_i <= '1';
                    heartbeat_counter_i <= 0;
                    if rx_valid_i = '1' then
                        pending_byte_i <= rx_byte_i;
                        pending_i <= '1';
                    else
                        pending_i <= '0';
                    end if;
                elsif pending_i = '0' and rx_valid_i = '1' then
                    pending_byte_i <= rx_byte_i;
                    pending_i <= '1';
                elsif heartbeat_counter_i = CLK_FREQ_HZ - 1 and tx_ready_i = '1' then
                    tx_byte_i <= x"55";
                    tx_valid_i <= '1';
                    heartbeat_counter_i <= 0;
                elsif heartbeat_counter_i < CLK_FREQ_HZ - 1 then
                    heartbeat_counter_i <= heartbeat_counter_i + 1;
                end if;
            end if;
        end if;
    end process;

    -- Smoke image never authorizes the external power stage.
    load_enable_o <= '0';

    -- Selected sensor buses are electrically passive/inactive in the first image.
    tmp_scl_io <= 'Z';
    tmp_sda_io <= 'Z';
    adxl_cs_n_o <= '1';
    adxl_sclk_o <= '0';
    adxl_mosi_o <= '0';
    ads_cs_n_o <= '1';
    ads_sclk_o <= '0';
    ads_din_o <= '0';

    -- Safety and sensor inputs remain present on the physical pinout but do not
    -- create any actuator authority in the smoke image.
end architecture;
