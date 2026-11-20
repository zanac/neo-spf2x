// ng_sfetch.v - fix layer (S ROM) fetch.  Behaviour from docs/TIMING.md s.3/s.8.
//
// On the rising edge of PCK2B the console presents on the P bus
//   tile = PBUS[11:0], pos = PBUS[15:12]
// and S2H1 selects the byte of the 16-bit word, so the byte offset inside the
// 32-byte canonical tile is {pos, s2h1}.  The data are stored in the "sdram1"
// layout (docs/FORMAT.md), 4 bytes per tile line, so both candidate bytes
// (s2h1 = 0 and 1) live in two different words: both are fetched on PCK2B and
// S2H1 only selects between them.
//
// Unverified: polarity of S2H1 and that {pos,s2h1} is the canonical offset.
`timescale 1ns/1ps
module ng_sfetch (
    input  wire        clk, rst,
    input  wire        pck2b,
    input  wire [23:0] pbus,
    input  wire        s2h1,
    input  wire [11:0] tile_mask,
    input  wire [31:0] s_base,
    output wire [7:0]  fixd,
    output wire        fvalid,        // both bytes of the latched word are in
    output reg         mem_req,
    output reg  [31:0] mem_addr,
    input  wire        mem_valid,
    input  wire [63:0] mem_rdata
);
    reg pd;
    always @(posedge clk) pd <= rst ? 1'b0 : pck2b;
    wire rise = pck2b & ~pd;

    wire [11:0] tile = pbus[11:0] & tile_mask;
    wire [3:0]  pos  = pbus[15:12];

    reg [31:0] base;          // address of the tile
    reg [3:0]  posq;
    reg        got, busy, pend;
    reg [31:0] wa, wb;        // word for s2h1 = 0 / 1

    // canonical offset {pos, s2h1}: q = off[4:3], r = off[2:0]
    function [1:0] slot(input [3:0] p, input s);
        reg [4:0] off;
        begin off = {p, s}; slot = off[4:3] + 2'd2; end
    endfunction

    // the two candidate bytes (s2h1 = 0 / 1) sit in consecutive 32-bit words
    // (rows r even and r + 1), i.e. in one aligned 8-byte burst
    always @(posedge clk) begin
        mem_req <= 1'b0;
        if (rst) begin got <= 0; busy <= 0; pend <= 0; end
        else begin
            if (rise) begin
                base <= s_base + {tile, 5'd0} + {pos[1:0], 3'b000};
                posq <= pos; got <= 0; pend <= 1;
            end
            if (mem_valid && busy) begin
                busy <= 0;
                if (!(rise || pend)) begin
                    wa <= mem_rdata[31:0]; wb <= mem_rdata[63:32]; got <= 1;
                end
            end else if (pend && !busy && !rise) begin
                mem_req <= 1'b1; mem_addr <= base; busy <= 1; pend <= 0;
            end
        end
    end
    assign fvalid = got;
    wire [31:0] w = s2h1 ? wb : wa;
    wire [1:0]  sl = slot(posq, s2h1);
    assign fixd = w >> {sl, 3'b000};
endmodule
