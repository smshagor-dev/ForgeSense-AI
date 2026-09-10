library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_sensor_link_tx is
end entity;

architecture sim of tb_sensor_link_tx is
    type byte_array_t is array (natural range <>) of std_logic_vector(7 downto 0);
    constant GOLDEN : byte_array_t(0 to 21) := (
        x"A5", x"5A", x"01", x"11", x"00", x"00", x"08", x"00",
        x"04", x"03", x"02", x"01", x"1F", x"01", x"8E", x"00",
        x"B4", x"05", x"07", x"00", x"46", x"51"
    );

    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal sample_trigger : std_logic := '0';
    signal timestamp_ms : unsigned(31 downto 0) := x"01020304";
    signal temperature_deci_c : signed(15 downto 0) := to_signed(287, 16);
    signal vibration_milli_g : unsigned(15 downto 0) := to_unsigned(142, 16);
    signal current_milli_a : unsigned(15 downto 0) := to_unsigned(1460, 16);
    signal sensor_flags : unsigned(15 downto 0) := to_unsigned(7, 16);
    signal tx_ready : std_logic := '1';
    signal tx_valid : std_logic;
    signal tx_byte : std_logic_vector(7 downto 0);
    signal sample_dropped : std_logic;
begin
    clk <= not clk after 5 ns;

    dut : entity work.sensor_link_tx
        port map (
            clk => clk,
            rst => rst,
            sample_trigger => sample_trigger,
            timestamp_ms => timestamp_ms,
            temperature_deci_c => temperature_deci_c,
            vibration_milli_g => vibration_milli_g,
            current_milli_a => current_milli_a,
            sensor_flags => sensor_flags,
            tx_ready => tx_ready,
            tx_valid => tx_valid,
            tx_byte => tx_byte,
            sample_dropped => sample_dropped
        );

    stimulus : process
        variable index : natural := 0;
    begin
        wait for 20 ns;
        wait until rising_edge(clk);
        rst <= '0';

        wait until rising_edge(clk);
        sample_trigger <= '1';
        wait until rising_edge(clk);
        sample_trigger <= '0';

        while index <= 21 loop
            wait until rising_edge(clk);
            if tx_valid = '1' then
                assert tx_byte = GOLDEN(index)
                    report "sensor frame byte mismatch"
                    severity failure;
                index := index + 1;
            end if;
        end loop;

        wait until rising_edge(clk);
        assert tx_valid = '0'
            report "transmitter did not return idle"
            severity failure;

        report "tb_sensor_link_tx PASS" severity note;
        wait;
    end process;
end architecture;
