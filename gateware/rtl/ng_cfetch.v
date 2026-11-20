// ng_cfetch.v - sprite (C ROM) fetch + pixel serializer for the AES cartridge.
//
// Replaces, together with the SDRAM, the C ROMs and the PRO-CT0 half of the
// NEO-ZMC2.  Behaviour is derived from docs/TIMING.md (Geolith / NeoGeo_MiSTer
// notes), written from scratch.  The C data in SDRAM must be in the "sdram1"
// layout of docs/FORMAT.md: 8 bytes per tile row, the first 4 for the
// CA4 = 0 half, byte lane k = bitplane k.
//
// Unverified modelling choices (see docs/GATEWARE.md):
//  * CA4 = 0 selects the first 4 bytes of the row  (hypothesis)
//  * within a 12M tick the pair is output as (gad = earlier pixel, gbd = later)
//  * EVEN is not used
`timescale 1ns/1ps
module ng_cfetch (
    input  wire        clk,         // fast clock, SDRAM domain
    input  wire        rst,
    input  wire        tick12,      // one clk pulse per falling edge of 12M
    // console side
    input  wire        pck1b,       // rising edge latches P0-P23
    input  wire [23:0] pbus,
    input  wire        ca4,
    input  wire        load,        // sampled on tick12
    input  wire        h,           // horizontal flip
    // configuration (from the MCU registers)
    input  wire [19:0] tile_mask,   // next power of two >= C tiles, minus 1
    input  wire [31:0] c_base,      // SDRAM byte address of the C region
    // pixel outputs, valid after the tick12 that sampled load / advanced
    output wire [3:0]  gad,
    output wire [3:0]  gbd,
    output wire        dota,
    output wire        dotb,
    // SDRAM word read port (in-order responses, 1 request per clk max)
    output reg         mem_req,
    output reg  [31:0] mem_addr,    // byte address, 4-byte aligned
    input  wire        mem_valid,
    input  wire [63:0] mem_rdata,
    // status
    output wire        rdy0,        // half 0 of the latched row is in
    output wire        rdy1
);
    // ---- capture P bus on PCK1B rising edge -------------------------------
    reg pck_d;
    always @(posedge clk) pck_d <= rst ? 1'b0 : pck1b;
    wire pck_rise = pck1b & ~pck_d;

    // tile = {PBUS[23:20], PBUS[15:0]}, row = PBUS[19:16]
    wire [19:0] tile = {pbus[23:20], pbus[15:0]} & tile_mask;
    wire [3:0]  row  = pbus[19:16];
    wire [31:0] row_addr = c_base + {tile, 7'd0} + {row, 3'd0};

    // ---- fetch: one 8-byte read (both halves of the row) ------------------
    reg        got;
    reg        busy;      // a read is outstanding
    reg        pend;      // a new row waits for the previous read to finish
    reg [31:0] a0;
    reg [31:0] w0, w1;

    always @(posedge clk) begin
        mem_req <= 1'b0;
        if (rst) begin got <= 0; busy <= 0; pend <= 0; end
        else begin
            if (pck_rise) begin          // a new row supersedes any old one
                a0 <= row_addr; got <= 0; pend <= 1;
            end
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
    assign rdy0 = got;
    assign rdy1 = got;

    // ---- serializer --------------------------------------------------------
    reg [7:0] l0, l1, l2, l3;       // lane k = bitplane k
    wire [31:0] sel = ca4 ? w1 : w0;

    always @(posedge clk) if (tick12) begin
        if (load) begin
            l0 <= sel[7:0];   l1 <= sel[15:8];
            l2 <= sel[23:16]; l3 <= sel[31:24];
        end else if (h) begin
            l0 <= {l0[5:0], 2'b0}; l1 <= {l1[5:0], 2'b0};
            l2 <= {l2[5:0], 2'b0}; l3 <= {l3[5:0], 2'b0};
        end else begin
            l0 <= {2'b0, l0[7:2]}; l1 <= {2'b0, l1[7:2]};
            l2 <= {2'b0, l2[7:2]}; l3 <= {2'b0, l3[7:2]};
        end
    end
    // h is sampled on the tick; for the loaded word the flip decides the
    // reading direction of the first pair
    reg hq;
    always @(posedge clk) if (tick12) hq <= h;
    wire hh = hq;

    assign gad = hh ? {l3[7], l2[7], l1[7], l0[7]} : {l3[0], l2[0], l1[0], l0[0]};
    assign gbd = hh ? {l3[6], l2[6], l1[6], l0[6]} : {l3[1], l2[1], l1[1], l0[1]};
    assign dota = |gad;
    assign dotb = |gbd;
endmodule
