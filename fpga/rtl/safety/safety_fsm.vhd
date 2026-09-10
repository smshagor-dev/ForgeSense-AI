library ieee;
use ieee.std_logic_1164.all;
use work.safety_pkg.all;

entity safety_fsm is
    port (
        clk : in std_logic;
        rst : in std_logic;
        startup_done : in std_logic;
        emergency : in std_logic;
        hard_warning : in std_logic;
        hard_critical : in std_logic;
        comm_timeout : in std_logic;
        ml_valid : in std_logic;
        ml_warning : in std_logic;
        ml_critical : in std_logic;
        recovery_req : in std_logic;
        state_code : out std_logic_vector(2 downto 0);
        load_enable : out std_logic;
        warning_active : out std_logic;
        fault_latched : out std_logic
    );
end entity;

architecture rtl of safety_fsm is
    signal state : safety_state_t := ST_STARTUP;
    signal latched : std_logic := '0';
begin
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state <= ST_STARTUP;
                latched <= '0';
            elsif emergency = '1' or hard_critical = '1' then
                state <= ST_FAULT_LATCHED;
                latched <= '1';
            else
                case state is
                    when ST_STARTUP =>
                        if comm_timeout = '1' then
                            state <= ST_SHUTDOWN;
                        elsif startup_done = '1' then
                            state <= ST_RUN;
                        end if;
                    when ST_RUN =>
                        if comm_timeout = '1' then
                            state <= ST_SHUTDOWN;
                        elsif ml_valid = '1' and ml_critical = '1' then
                            state <= ST_SHUTDOWN;
                        elsif hard_warning = '1' or (ml_valid = '1' and ml_warning = '1') then
                            state <= ST_WARNING;
                        end if;
                    when ST_WARNING =>
                        if comm_timeout = '1' then
                            state <= ST_SHUTDOWN;
                        elsif ml_valid = '1' and ml_critical = '1' then
                            state <= ST_SHUTDOWN;
                        elsif hard_warning = '0' and (ml_valid = '0' or ml_warning = '0') then
                            state <= ST_RUN;
                        end if;
                    when ST_SHUTDOWN =>
                        if recovery_req = '1' and comm_timeout = '0' and hard_warning = '0' and hard_critical = '0' then
                            state <= ST_RECOVERY;
                        end if;
                    when ST_FAULT_LATCHED =>
                        if recovery_req = '1' and emergency = '0' and hard_critical = '0' then
                            latched <= '0';
                            state <= ST_RECOVERY;
                        end if;
                    when ST_RECOVERY =>
                        state <= ST_STARTUP;
                end case;
            end if;
        end if;
    end process;

    state_code <= state_to_slv(state);
    load_enable <= '1' when state = ST_RUN or state = ST_WARNING else '0';
    warning_active <= '1' when state = ST_WARNING else '0';
    fault_latched <= latched;
end architecture;
