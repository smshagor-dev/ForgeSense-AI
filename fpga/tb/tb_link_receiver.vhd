library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_link_receiver is
end entity;

architecture sim of tb_link_receiver is
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal rx_valid : std_logic := '0';
    signal rx_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal frame_valid : std_logic;
    signal frame_rejected : std_logic;
    signal sequence_number : unsigned(15 downto 0);
    signal timestamp_ms : unsigned(31 downto 0);
    signal model_id : unsigned(15 downto 0);
    signal model_version : unsigned(15 downto 0);
    signal schema : unsigned(15 downto 0);
    signal valid_flag : std_logic;
    signal anomaly_q15 : unsigned(15 downto 0);
    signal health_class : unsigned(7 downto 0);
    signal confidence_q8 : unsigned(7 downto 0);
    signal age_ms : unsigned(15 downto 0);
    type byte_array_t is array (natural range <>) of std_logic_vector(7 downto 0);
    constant GOLDEN : byte_array_t(0 to 27) := (
        x"A5",x"5A",x"01",x"10",x"07",x"00",x"0E",x"00",
        x"39",x"30",x"00",x"00",x"01",x"00",x"01",x"00",
        x"01",x"00",x"01",x"00",x"FF",x"67",x"01",x"E0",
        x"19",x"00",x"E3",x"C8"
    );
begin
    clk <= not clk after 5 ns;

    dut : entity work.link_receiver
        port map (
            clk => clk, rst => rst, rx_valid => rx_valid, rx_byte => rx_byte,
            frame_valid => frame_valid, frame_rejected => frame_rejected,
            sequence_number => sequence_number, timestamp_ms => timestamp_ms,
            model_id => model_id, model_version => model_version,
            feature_schema_version => schema, observation_valid_flag => valid_flag,
            anomaly_q15 => anomaly_q15, health_class => health_class,
            confidence_q8 => confidence_q8, inference_age_ms => age_ms
        );

    stimulus : process
        procedure send_byte(constant value : std_logic_vector(7 downto 0)) is
        begin
            rx_byte <= value;
            rx_valid <= '1';
            wait until rising_edge(clk);
            wait for 1 ns;
            rx_valid <= '0';
            wait until falling_edge(clk);
        end procedure;
        variable corrupt : std_logic_vector(7 downto 0);
    begin
        wait for 20 ns;
        wait until rising_edge(clk);
        rst <= '0';
        wait until falling_edge(clk);
        send_byte(x"00");
        send_byte(x"44");
        for i in GOLDEN'range loop
            send_byte(GOLDEN(i));
        end loop;
        assert frame_valid = '1' report "golden frame not accepted" severity error;
        assert sequence_number = to_unsigned(7, 16) severity error;
        assert timestamp_ms = to_unsigned(12345, 32) severity error;
        assert model_id = to_unsigned(1, 16) severity error;
        assert model_version = to_unsigned(1, 16) severity error;
        assert schema = to_unsigned(1, 16) severity error;
        assert valid_flag = '1' severity error;
        assert anomaly_q15 = to_unsigned(16#67FF#, 16) severity error;
        assert health_class = to_unsigned(1, 8) severity error;
        assert confidence_q8 = to_unsigned(16#E0#, 8) severity error;
        assert age_ms = to_unsigned(25, 16) severity error;

        for i in GOLDEN'range loop
            corrupt := GOLDEN(i);
            if i = 20 then
                corrupt := GOLDEN(i) xor x"01";
            end if;
            send_byte(corrupt);
        end loop;
        assert frame_rejected = '1' report "CRC-corrupt frame not rejected" severity error;
        report "tb_link_receiver PASS" severity note;
        wait;
    end process;
end architecture;
