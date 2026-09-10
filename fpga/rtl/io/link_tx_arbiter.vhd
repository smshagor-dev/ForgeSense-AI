library ieee;
use ieee.std_logic_1164.all;

entity link_tx_arbiter is
    port (
        clk : in std_logic;
        rst : in std_logic;
        status_valid : in std_logic;
        status_byte : in std_logic_vector(7 downto 0);
        status_ready : out std_logic;
        sensor_valid : in std_logic;
        sensor_byte : in std_logic_vector(7 downto 0);
        sensor_ready : out std_logic;
        uart_ready : in std_logic;
        uart_valid : out std_logic;
        uart_byte : out std_logic_vector(7 downto 0)
    );
end entity;

architecture rtl of link_tx_arbiter is
    type grant_t is (GRANT_NONE, GRANT_STATUS, GRANT_SENSOR);
    signal grant : grant_t := GRANT_NONE;
begin
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                grant <= GRANT_NONE;
            else
                case grant is
                    when GRANT_NONE =>
                        if status_valid = '1' then
                            grant <= GRANT_STATUS;
                        elsif sensor_valid = '1' then
                            grant <= GRANT_SENSOR;
                        end if;
                    when GRANT_STATUS =>
                        if status_valid = '0' then
                            grant <= GRANT_NONE;
                        end if;
                    when GRANT_SENSOR =>
                        if sensor_valid = '0' then
                            grant <= GRANT_NONE;
                        end if;
                end case;
            end if;
        end if;
    end process;

    status_ready <= uart_ready when grant = GRANT_STATUS else '0';
    sensor_ready <= uart_ready when grant = GRANT_SENSOR else '0';
    uart_valid <= status_valid when grant = GRANT_STATUS else
                  sensor_valid when grant = GRANT_SENSOR else '0';
    uart_byte <= status_byte when grant = GRANT_STATUS else
                 sensor_byte when grant = GRANT_SENSOR else (others => '0');
end architecture;
