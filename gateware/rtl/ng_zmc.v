// ng_zmc.v - Z80 bank switching of the M ROM (NEO-ZMC part).  (docs/TIMING.md s.5)
//
// Z80 map: 0000-7FFF fixed; 8000-BFFF 16 KiB bank0; C000-DFFF 8 KiB bank1;
// E000-EFFF 4 KiB bank2; F000-F7FF 2 KiB bank3; F800-FFFF Z80 RAM (not ours).
// A Z80 port read selects the bank: port 0x0B -> bank0, 0x0A -> 1, 0x09 -> 2,
// 0x08 -> 3, the bank number being A15-A8 of that access.  Windows are 19-bit
// wide (512 KiB reach), reset = identity mapping.
`timescale 1ns/1ps
module ng_zmc (
    input  wire        clk, rst,
    input  wire        io_rd,        // pulse: Z80 port read (IORQ+RD)
    input  wire [15:0] za,           // Z80 address bus (port: A15-A8 = bank)
    output wire [18:0] m_addr,       // byte address in the M ROM (valid for memory reads)
    output wire        m_sel         // address is in a ROM window (not RAM)
);
    reg [7:0] n0, n1, n2, n3;
    always @(posedge clk) begin
        if (rst) begin n0 <= 8'd2; n1 <= 8'd6; n2 <= 8'd14; n3 <= 8'd30; end
        else if (io_rd && za[7:2] == 6'b000010) begin   // ports 0x08-0x0B
            case (za[1:0])
                2'd3: n0 <= za[15:8] & 8'h1F;
                2'd2: n1 <= za[15:8] & 8'h3F;
                2'd1: n2 <= za[15:8] & 8'h7F;
                2'd0: n3 <= za[15:8];
            endcase
        end
    end
    reg [18:0] r;
    always @* begin
        if (!za[15])              r = {4'd0, za[14:0]};
        else if (za[15:14] == 2'b10) r = {n0[4:0], za[13:0]};
        else if (za[15:13] == 3'b110) r = {n1[5:0], za[12:0]};
        else if (za[15:12] == 4'hE)   r = {n2[6:0], za[11:0]};
        else                          r = {n3[7:0], za[10:0]};
    end
    assign m_addr = r;
    assign m_sel  = (za < 16'hF800);
endmodule
