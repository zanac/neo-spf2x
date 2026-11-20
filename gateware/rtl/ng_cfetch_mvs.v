// ng_cfetch_mvs.v - sprite (C ROM) fetch for the MVS cartridge.
//
// On the MVS the console does the serialization: the CHA board only has to
// answer an address on P0-P23 (latched by PCK1B) with 32 bits on CR0-CR31, one
// half of the 64-bit tile row selected by CA4.  So this module is the AES
// ng_cfetch without the serializer: it fetches the whole 8-byte row (both
// halves) from SDRAM in the "sdram1" layout and presents
//     cr = CA4 ? second 4 bytes : first 4 bytes
// as a pure combinational mux, so CA4 may change at any time.
//
// Unverified modelling choices (docs/MVS.md):
//  * which 4-byte half is selected by CA4 = 0 (same hypothesis as the AES)
//  * CR[7:0] = byte 0 of the half = lane 0 (bitplane 0)... i.e. CRn is bit n of
//    the little-endian 32-bit word of the sdram1 layout (see tools/ngpk.py)
//  * the deadline between PCK1B and the console sampling CR is not known;
//    `ready` tells whether the row has arrived, the console cannot be stalled.
`timescale 1ns/1ps
module ng_cfetch_mvs (
    input  wire        clk,
    input  wire        rst,
    input  wire        pck1b,
    input  wire [23:0] pbus,
    input  wire        ca4,
    input  wire [19:0] tile_mask,
    input  wire [31:0] c_base,
    output wire [31:0] cr,
    output wire        ready,
    output reg         mem_req,
    output reg  [31:0] mem_addr,
    input  wire        mem_valid,
    input  wire [63:0] mem_rdata
);
    reg pck_d;
    always @(posedge clk) pck_d <= rst ? 1'b0 : pck1b;
    wire pck_rise = pck1b & ~pck_d;

    wire [19:0] tile = {pbus[23:20], pbus[15:0]} & tile_mask;
    wire [3:0]  row  = pbus[19:16];
    wire [31:0] row_addr = c_base + {tile, 7'd0} + {row, 3'd0};

    reg        got, busy, pend;
    reg [31:0] a0, w0, w1;
    always @(posedge clk) begin
        mem_req <= 1'b0;
        if (rst) begin got <= 0; busy <= 0; pend <= 0; end
        else begin
            if (pck_rise) begin a0 <= row_addr; got <= 0; pend <= 1; end
            if (mem_valid && busy) begin
                busy <= 0;
                if (!(pck_rise || pend)) begin
                    w0 <= mem_rdata[31:0]; w1 <= mem_rdata[63:32]; got <= 1;
                end
            end else if (pend && !busy && !pck_rise) begin
                mem_req <= 1'b1; mem_addr <= a0; busy <= 1; pend <= 0;
            end
        end
    end
    assign ready = got;
    assign cr = ca4 ? w1 : w0;
endmodule
