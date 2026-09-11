library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.crc16_ccitt_pkg.all;

entity tb_calibration_diag_tx is
end entity;

architecture sim of tb_calibration_diag_tx is
    constant CLK_PERIOD : time := 10 ns;
    type byte_array30_t is array (0 to 29) of std_logic_vector(7 downto 0);
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal trigger : std_logic := '0';
    signal tx_valid, dropped : std_logic;
    signal tx_byte : std_logic_vector(7 downto 0);
    signal captured : byte_array30_t := (others => (others => '0'));
    signal captured_count : natural range 0 to 30 := 0;
begin
    clk <= not clk after CLK_PERIOD / 2;

    dut : entity work.calibration_diag_tx
        port map (
            clk => clk,
            rst => rst,
            sample_trigger => trigger,
            timestamp_ms => unsigned'(x"11223344"),
            ads_ch0_raw => to_signed(-2, 24),
            ads_ch1_raw => to_signed(16#123456#, 24),
            tmp_deci_c => to_signed(-123, 16),
            adxl_x_milli_g => to_signed(-1, 16),
            adxl_y_milli_g => to_signed(2, 16),
            adxl_z_milli_g => to_signed(1000, 16),
            diagnostic_flags => to_unsigned(16#013F#, 16),
            tx_ready => '1',
            tx_valid => tx_valid,
            tx_byte => tx_byte,
            sample_dropped => dropped
        );

    capture : process(clk)
    begin
        if rising_edge(clk) then
            if tx_valid = '1' and captured_count < 30 then
                captured(captured_count) <= tx_byte;
                captured_count <= captured_count + 1;
            end if;
        end if;
    end process;

    stimulus : process
        variable crc : unsigned(15 downto 0);
    begin
        wait for 4 * CLK_PERIOD;
        wait until rising_edge(clk);
        rst <= '0';
        wait until rising_edge(clk);
        trigger <= '1';
        wait until rising_edge(clk);
        trigger <= '0';

        wait until captured_count = 30;
        wait until rising_edge(clk);

        assert captured(0) = x"A5" and captured(1) = x"5A" report "bad calibration SOF" severity failure;
        assert captured(2) = x"01" and captured(3) = x"32" report "bad calibration version/type" severity failure;
        assert captured(4) = x"00" and captured(5) = x"00" report "bad initial sequence" severity failure;
        assert captured(6) = x"10" and captured(7) = x"00" report "bad calibration payload length" severity failure;
        assert captured(8) = x"44" and captured(9) = x"33" and captured(10) = x"22" and captured(11) = x"11"
            report "bad calibration timestamp" severity failure;
        assert captured(12) = x"FE" and captured(13) = x"FF" and captured(14) = x"FF"
            report "bad signed ADS channel 0 packing" severity failure;
        assert captured(15) = x"56" and captured(16) = x"34" and captured(17) = x"12"
            report "bad ADS channel 1 packing" severity failure;
        assert captured(18) = x"85" and captured(19) = x"FF" report "bad TMP117 packing" severity failure;
        assert captured(20) = x"FF" and captured(21) = x"FF" report "bad ADXL X packing" severity failure;
        assert captured(22) = x"02" and captured(23) = x"00" report "bad ADXL Y packing" severity failure;
        assert captured(24) = x"E8" and captured(25) = x"03" report "bad ADXL Z packing" severity failure;
        assert captured(26) = x"3F" and captured(27) = x"01" report "bad diagnostic flags packing" severity failure;

        crc := to_unsigned(16#FFFF#, 16);
        for i in 2 to 27 loop
            crc := crc16_next(crc, captured(i));
        end loop;
        assert captured(28) = std_logic_vector(crc(7 downto 0))
            report "bad calibration CRC low byte" severity failure;
        assert captured(29) = std_logic_vector(crc(15 downto 8))
            report "bad calibration CRC high byte" severity failure;
        assert dropped = '0' report "unexpected diagnostic sample drop" severity failure;

        report "tb_calibration_diag_tx PASS" severity note;
        wait;
    end process;
end architecture;
