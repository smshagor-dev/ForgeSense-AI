library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity intelligence_gate is
    generic (
        EXPECTED_MODEL_ID : natural := 1;
        EXPECTED_MODEL_VERSION : natural := 1;
        EXPECTED_FEATURE_SCHEMA : natural := 1;
        MAX_INFERENCE_AGE_MS : natural := 1500
    );
    port (
        clk : in std_logic;
        rst : in std_logic;
        frame_valid : in std_logic;
        observation_valid_flag : in std_logic;
        sequence_number : in unsigned(15 downto 0);
        model_id : in unsigned(15 downto 0);
        model_version : in unsigned(15 downto 0);
        feature_schema_version : in unsigned(15 downto 0);
        inference_age_ms : in unsigned(15 downto 0);
        accepted : out std_logic;
        watchdog_kick : out std_logic
    );
end entity;

architecture rtl of intelligence_gate is
    signal have_sequence : std_logic := '0';
    signal last_sequence : unsigned(15 downto 0) := (others => '0');
    function is_newer(candidate : unsigned(15 downto 0); previous : unsigned(15 downto 0)) return boolean is
        variable delta : unsigned(15 downto 0);
    begin
        delta := candidate - previous;
        return delta /= to_unsigned(0, 16) and delta < to_unsigned(16#8000#, 16);
    end function;
begin
    process (clk)
        variable compatible : boolean;
        variable fresh_seq : boolean;
    begin
        if rising_edge(clk) then
            accepted <= '0';
            watchdog_kick <= '0';
            if rst = '1' then
                have_sequence <= '0';
                last_sequence <= (others => '0');
            elsif frame_valid = '1' then
                compatible := observation_valid_flag = '1' and
                    model_id = to_unsigned(EXPECTED_MODEL_ID, 16) and
                    model_version = to_unsigned(EXPECTED_MODEL_VERSION, 16) and
                    feature_schema_version = to_unsigned(EXPECTED_FEATURE_SCHEMA, 16) and
                    inference_age_ms <= to_unsigned(MAX_INFERENCE_AGE_MS, 16);
                fresh_seq := have_sequence = '0' or is_newer(sequence_number, last_sequence);
                if compatible and fresh_seq then
                    accepted <= '1';
                    watchdog_kick <= '1';
                    last_sequence <= sequence_number;
                    have_sequence <= '1';
                end if;
            end if;
        end if;
    end process;
end architecture;
