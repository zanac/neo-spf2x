// ng_mvs_pdec.v - MVS PROG strobes -> the address/strobe interface of ng_pbank.
//
// The MVS console already decodes the 68k space for the cartridge (PROG pins
// ROMOEU/ROMOEL, PORTOEU/PORTOEL, PORTWEU/PORTWEL, active low; A1-A19 and D0-D15
// are on the connector, A20+ are not).  Hypothesis (docs/MVS.md, to verify on a
// console / with the wiki 'Signals' page):
//    ROMOEx low        read of $000000-$0FFFFF   (P1, fixed)
//    PORTOEx low       read of $200000-$2FFFFF   (banked window)
//    PORTWEx low       write in $200000-$2FFFFF  (bank latch, magic word)
// This module rebuilds a 24-bit word address with A23..A20 = 0x0 or 0x2 and
// produces 1-clk rd/wr pulses on the falling edge of the strobe (synchronised).
`timescale 1ns/1ps
module ng_mvs_pdec (
    input  wire        clk, rst,
    input  wire [19:1] a,
    input  wire        romoeu_n, romoel_n, portoeu_n, portoel_n,
    input  wire        portweu_n, portwel_n,
    output reg  [22:0] p_a,
    output reg         p_rd, p_wr
);
    wire ro = ~(romoeu_n & romoel_n);
    wire po = ~(portoeu_n & portoel_n);
    wire pw = ~(portweu_n & portwel_n);
    reg ro_d, po_d, pw_d, ro_q, po_q, pw_q;
    always @(posedge clk) begin
        ro_q <= ro; po_q <= po; pw_q <= pw;     // 2-FF style synchronisers
        ro_d <= ro_q; po_d <= po_q; pw_d <= pw_q;
        p_rd <= 1'b0; p_wr <= 1'b0;
        if (rst) begin ro_d <= 0; po_d <= 0; pw_d <= 0; end
        else begin
            if ((ro_q && !ro_d) || (po_q && !po_d)) begin
                p_a <= {(po_q ? 4'h2 : 4'h0), a}; p_rd <= 1'b1;
            end
            if (pw_q && !pw_d) begin
                p_a <= {4'h2, a}; p_wr <= 1'b1;
            end
        end
    end
endmodule
