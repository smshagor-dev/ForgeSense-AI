library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_status_link_tx is
end entity;

architecture sim of tb_status_link_tx is
    type byte_array_t is array (natural range <>) of std_logic_vector(7 downto 0);
    constant GOLDEN : byte_array_t(0 to 17) := (
        x"A5", x"5A", x"01", x"30", x"00", x"00", x"04", x"00",
        x"04", x"03", x"02", x"01", x"02", x"0B", x"49", x"00",
        x"D1", x"18"
    );

    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal status_trigger : std_logic := '0';
    signal timestamp_ms : unsigned(31 downto 0) := x"01020304";
    signal state_code : std_logic_vector(2 downto 0) := "010";
    signal control_flags : unsigned(7 downto 0) := x"0B";
    signal safety_flags : unsigned(15 downto 0) := x"0049";
    signal tx_ready : std_logic := '1';
    signal tx_valid : std_logic;
    signal tx_byte : std_logic_vector(7 downto 0);
begin
    clk <= not clk after 5 ns;

    dut : entity work.status_link_tx
        port map (
            clk => clk,
            rst => rst,
            status_trigger => status_trigger,
            timestamp_ms => timestamp_ms,
            state_code => state_code,
            control_flags => control_flags,
            safety_flags => safety_flags,
            tx_ready => tx_ready,
            tx_valid => tx_valid,
            tx_byte => tx_byte
        );

    stimulus : process
        variable index : natural := 0;
    begin
        wait for 20 ns;
        wait until rising_edge(clk);
        rst <= '0';

        wait until rising_edge(clk);
        status_trigger <= '1';
        wait until rising_edge(clk);
        status_trigger <= '0';

        while index <= 17 loop
            wait until rising_edge(clk);
            if tx_valid = '1' then
                assert tx_byte = GOLDEN(index)
                    report "status frame byte mismatch"
                    severity failure;
                index := index + 1;
            end if;
        end loop;

        wait until rising_edge(clk);
        assert tx_valid = '0'
            report "status transmitter did not return idle"
            severity failure;

        report "tb_status_link_tx PASS" severity note;
        wait;
    end process;
end architecture;
