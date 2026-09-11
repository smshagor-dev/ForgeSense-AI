library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity adxl355_spi_model is
    port (
        cs_n : in std_logic;
        sclk : in std_logic;
        mosi : in std_logic;
        miso : out std_logic;
        force_bad_id : in std_logic := '0';
        x_raw20 : in signed(19 downto 0) := to_signed(10000, 20);
        y_raw20 : in signed(19 downto 0) := to_signed(-10000, 20);
        z_raw20 : in signed(19 downto 0) := to_signed(20000, 20)
    );
end entity;

architecture behavioral of adxl355_spi_model is
    signal miso_reg : std_logic := '0';
    signal filter_reg : std_logic_vector(7 downto 0) := x"00";
    signal range_reg : std_logic_vector(7 downto 0) := x"00";
    signal power_reg : std_logic_vector(7 downto 0) := x"01";

    function register_value(
        address : natural;
        bad_id : std_logic;
        filter_value : std_logic_vector(7 downto 0);
        range_value : std_logic_vector(7 downto 0);
        power_value : std_logic_vector(7 downto 0);
        x_value : signed(19 downto 0);
        y_value : signed(19 downto 0);
        z_value : signed(19 downto 0)
    ) return std_logic_vector is
        variable packed_x, packed_y, packed_z : std_logic_vector(23 downto 0);
    begin
        packed_x := std_logic_vector(x_value) & "0000";
        packed_y := std_logic_vector(y_value) & "0000";
        packed_z := std_logic_vector(z_value) & "0000";
        case address is
            when 16#00# => return x"AD";
            when 16#01# => return x"1D";
            when 16#02# => if bad_id = '1' then return x"00"; else return x"ED"; end if;
            when 16#08# => return packed_x(23 downto 16);
            when 16#09# => return packed_x(15 downto 8);
            when 16#0A# => return packed_x(7 downto 0);
            when 16#0B# => return packed_y(23 downto 16);
            when 16#0C# => return packed_y(15 downto 8);
            when 16#0D# => return packed_y(7 downto 0);
            when 16#0E# => return packed_z(23 downto 16);
            when 16#0F# => return packed_z(15 downto 8);
            when 16#10# => return packed_z(7 downto 0);
            when 16#28# => return filter_value;
            when 16#2C# => return range_value;
            when 16#2D# => return power_value;
            when others => return x"00";
        end case;
    end function;
begin
    miso <= miso_reg;

    process(cs_n, sclk)
        variable bit_index : integer range 0 to 7 := 7;
        variable byte_index : natural := 0;
        variable rx_shift : std_logic_vector(7 downto 0) := (others => '0');
        variable completed : std_logic_vector(7 downto 0);
        variable address : natural range 0 to 127 := 0;
        variable is_read : boolean := false;
        variable tx_byte : std_logic_vector(7 downto 0) := (others => '0');
    begin
        if falling_edge(cs_n) then
            bit_index := 7;
            byte_index := 0;
            rx_shift := (others => '0');
            address := 0;
            is_read := false;
            tx_byte := (others => '0');
            miso_reg <= '0';
        elsif rising_edge(cs_n) then
            miso_reg <= '0';
        elsif cs_n = '0' and rising_edge(sclk) then
            rx_shift(bit_index) := mosi;
        elsif cs_n = '0' and falling_edge(sclk) then
            if bit_index = 0 then
                completed := rx_shift;
                if byte_index = 0 then
                    address := to_integer(unsigned(completed(7 downto 1)));
                    is_read := completed(0) = '1';
                    if is_read then
                        tx_byte := register_value(address, force_bad_id, filter_reg, range_reg, power_reg, x_raw20, y_raw20, z_raw20);
                        miso_reg <= tx_byte(7);
                    else
                        miso_reg <= '0';
                    end if;
                else
                    if is_read then
                        address := (address + 1) mod 128;
                        tx_byte := register_value(address, force_bad_id, filter_reg, range_reg, power_reg, x_raw20, y_raw20, z_raw20);
                        miso_reg <= tx_byte(7);
                    else
                        case address is
                            when 16#28# => filter_reg <= completed;
                            when 16#2C# => range_reg <= completed;
                            when 16#2D# => power_reg <= completed;
                            when others => null;
                        end case;
                        miso_reg <= '0';
                    end if;
                end if;
                byte_index := byte_index + 1;
                bit_index := 7;
                rx_shift := (others => '0');
            else
                bit_index := bit_index - 1;
                if is_read and byte_index > 0 then
                    miso_reg <= tx_byte(bit_index - 1);
                end if;
            end if;
        end if;
    end process;
end architecture;
