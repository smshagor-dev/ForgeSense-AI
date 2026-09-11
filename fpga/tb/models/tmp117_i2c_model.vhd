library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tmp117_i2c_model is
    port (
        scl : in std_logic;
        sda : in std_logic;
        sda_drive_low : out std_logic;
        force_nack : in std_logic := '0';
        force_bad_id : in std_logic := '0';
        temperature_raw : in signed(15 downto 0) := to_signed(16#0C80#, 16)
    );
end entity;

architecture behavioral of tmp117_i2c_model is
    type phase_t is (
        IDLE, RECV_ADDRESS, ACK_ADDRESS_DRIVE, ACK_ADDRESS_SAMPLE,
        RECV_REGISTER, ACK_REGISTER_DRIVE, ACK_REGISTER_SAMPLE,
        SEND_DATA, WAIT_MASTER_ACK
    );
    signal sda_low : std_logic := '0';
begin
    sda_drive_low <= sda_low;

    process(scl, sda)
        variable phase : phase_t := IDLE;
        variable shift_byte : std_logic_vector(7 downto 0) := (others => '0');
        variable bit_count : integer range 0 to 7 := 0;
        variable register_pointer : std_logic_vector(7 downto 0) := x"00";
        variable address_byte : std_logic_vector(7 downto 0) := (others => '0');
        variable address_ok : boolean := false;
        variable read_cycle : boolean := false;
        variable send_word : std_logic_vector(15 downto 0) := (others => '0');
        variable send_byte : std_logic_vector(7 downto 0) := (others => '0');
        variable send_bit : integer range 0 to 7 := 7;
        variable send_index : integer range 0 to 1 := 0;
        variable completed : std_logic_vector(7 downto 0);
    begin
        if sda'event and sda = '0' and scl = '1' then
            -- START or repeated START.
            phase := RECV_ADDRESS;
            bit_count := 0;
            shift_byte := (others => '0');
            sda_low <= '0';
        elsif sda'event and sda = '1' and scl = '1' then
            -- STOP.
            phase := IDLE;
            sda_low <= '0';
        elsif rising_edge(scl) then
            case phase is
                when RECV_ADDRESS | RECV_REGISTER =>
                    completed := shift_byte(6 downto 0) & sda;
                    shift_byte := completed;
                    if bit_count = 7 then
                        bit_count := 0;
                        if phase = RECV_ADDRESS then
                            address_byte := completed;
                            address_ok := completed(7 downto 1) = "1001000";
                            read_cycle := completed(0) = '1';
                            phase := ACK_ADDRESS_DRIVE;
                        else
                            register_pointer := completed;
                            phase := ACK_REGISTER_DRIVE;
                        end if;
                    else
                        bit_count := bit_count + 1;
                    end if;

                when WAIT_MASTER_ACK =>
                    -- ACK after the high byte requests the low byte. NACK ends the read.
                    if sda = '0' and send_index = 0 then
                        send_index := 1;
                        send_byte := send_word(7 downto 0);
                        send_bit := 7;
                    else
                        phase := IDLE;
                    end if;

                when others => null;
            end case;
        elsif falling_edge(scl) then
            case phase is
                when ACK_ADDRESS_DRIVE =>
                    if address_ok and force_nack = '0' then sda_low <= '1';
                    else sda_low <= '0'; end if;
                    phase := ACK_ADDRESS_SAMPLE;

                when ACK_ADDRESS_SAMPLE =>
                    sda_low <= '0';
                    if not address_ok or force_nack = '1' then
                        phase := IDLE;
                    elsif read_cycle then
                        if register_pointer = x"0F" then
                            if force_bad_id = '1' then send_word := x"0000";
                            else send_word := x"0117"; end if;
                        else
                            send_word := std_logic_vector(temperature_raw);
                        end if;
                        send_index := 0;
                        send_byte := send_word(15 downto 8);
                        send_bit := 7;
                        if send_byte(7) = '0' then sda_low <= '1'; else sda_low <= '0'; end if;
                        phase := SEND_DATA;
                    else
                        bit_count := 0;
                        shift_byte := (others => '0');
                        phase := RECV_REGISTER;
                    end if;

                when ACK_REGISTER_DRIVE =>
                    if force_nack = '0' then sda_low <= '1'; else sda_low <= '0'; end if;
                    phase := ACK_REGISTER_SAMPLE;

                when ACK_REGISTER_SAMPLE =>
                    sda_low <= '0';
                    phase := IDLE; -- controller follows with repeated START.

                when SEND_DATA =>
                    if send_bit = 0 then
                        sda_low <= '0';
                        phase := WAIT_MASTER_ACK;
                    else
                        send_bit := send_bit - 1;
                        if send_byte(send_bit) = '0' then sda_low <= '1'; else sda_low <= '0'; end if;
                    end if;

                when WAIT_MASTER_ACK =>
                    if send_index = 1 and send_bit = 7 then
                        if send_byte(7) = '0' then sda_low <= '1'; else sda_low <= '0'; end if;
                        phase := SEND_DATA;
                    end if;

                when others => null;
            end case;
        end if;
    end process;
end architecture;
