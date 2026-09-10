library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_sensor_frontend is
end entity;

architecture sim of tb_sensor_frontend is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal temp_raw_valid, current_raw_valid, vib_valid : std_logic := '0';
    signal temp_raw, current_raw : signed(23 downto 0) := (others => '0');
    signal vib_raw : signed(15 downto 0) := (others => '0');
    signal temp_update, current_update, vib_update : std_logic;
    signal temp_out : signed(15 downto 0);
    signal current_out, vib_out : unsigned(15 downto 0);
    signal temp_sat, current_sat : std_logic;
begin
    clk <= not clk after 5 ns;

    dut : entity work.sensor_frontend
        generic map (
            TEMP_RAW_ZERO => 0,
            TEMP_GAIN_NUMERATOR => 1,
            TEMP_GAIN_DENOMINATOR => 1,
            CURRENT_RAW_ZERO => 100,
            CURRENT_GAIN_NUMERATOR => 10,
            CURRENT_GAIN_DENOMINATOR => 1,
            VIBRATION_WINDOW_SAMPLES => 2
        )
        port map (
            clk => clk,
            rst => rst,
            temperature_raw_valid => temp_raw_valid,
            temperature_raw => temp_raw,
            current_raw_valid => current_raw_valid,
            current_raw => current_raw,
            vibration_sample_valid => vib_valid,
            vibration_conditioned_milli_g => vib_raw,
            temperature_update => temp_update,
            temperature_deci_c => temp_out,
            current_update => current_update,
            current_milli_a => current_out,
            vibration_update => vib_update,
            vibration_milli_g_rms => vib_out,
            temperature_numeric_saturated => temp_sat,
            current_numeric_saturated => current_sat
        );

    stimulus : process
    begin
        wait for 30 ns;
        rst <= '0';
        wait until rising_edge(clk);

        temp_raw <= to_signed(250, 24);
        temp_raw_valid <= '1';
        current_raw <= to_signed(350, 24);
        current_raw_valid <= '1';
        wait until rising_edge(clk);
        temp_raw_valid <= '0';
        current_raw_valid <= '0';
        wait for 1 ns;
        assert temp_update = '1' and temp_out = to_signed(250, 16)
            report "temperature calibration mismatch" severity failure;
        assert current_update = '1' and current_out = to_unsigned(2500, 16)
            report "current calibration mismatch" severity failure;
        assert temp_sat = '0' and current_sat = '0'
            report "unexpected calibration saturation" severity failure;

        vib_raw <= to_signed(3000, 16);
        vib_valid <= '1';
        wait until rising_edge(clk);
        vib_raw <= to_signed(4000, 16);
        wait until rising_edge(clk);
        vib_valid <= '0';
        wait for 1 ns;
        assert vib_update = '1' and vib_out = to_unsigned(3535, 16)
            report "vibration RMS mismatch" severity failure;

        temp_raw <= to_signed(100000, 24);
        temp_raw_valid <= '1';
        wait until rising_edge(clk);
        temp_raw_valid <= '0';
        wait for 1 ns;
        assert temp_update = '1' and temp_sat = '1'
            report "numeric saturation was not reported" severity failure;

        report "tb_sensor_frontend PASS" severity note;
        wait;
    end process;
end architecture;
