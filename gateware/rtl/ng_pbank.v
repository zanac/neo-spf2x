// ng_pbank.v - 68k side: P ROM read path and bank latch.  (docs/TIMING.md s.4)
//
// * 68k $000000-$0FFFFF: P1, fixed, SDRAM P_BASE + addr
// * 68k $200000-$2FFFFF: 1 MiB window; bank n is at P offset 1 MiB * (n + 1)
// * any write in the window latches D[7:0] & bank_mask (the wiki describes a
//   latch of D0/D1 only, i.e. bank_mask = 3; larger games need more bits and
//   the MCU programs the mask).  The latch clears on reset.
// The P region is stored in 68k byte order, so a 16-bit read is the two bytes
// in memory order, big-endian.
`timescale 1ns/1ps
module ng_pbank (
    input  wire        clk, rst,
    input  wire [7:0]  bank_mask,
    input  wire [31:0] p_base,
    // 68k bus (word address, A23..A1 -> a[22:0] = A23..A1)
    input  wire [22:0] a,
    input  wire        rd,          // read request, pulse (1 clk)
    input  wire        wr,          // write strobe, pulse (1 clk)
    input  wire [15:0] wdata,
    output reg  [15:0] rdata,
    output reg         rvalid,      // pulse when rdata is ready
    output wire        in_cart,     // address decodes to P ROM
    // SDRAM word port
    output reg         mem_req,
    output reg  [31:0] mem_addr,
    input  wire        mem_valid,
    input  wire [63:0] mem_rdata
);
    reg [7:0] bank;
    wire [23:0] ba = {a, 1'b0};                    // byte address
    wire win  = (ba[23:20] == 4'h2);
    wire p1   = (ba[23:20] == 4'h0);
    assign in_cart = win | p1;

    always @(posedge clk)
        if (rst) bank <= 0;
        else if (wr && win) bank <= wdata[7:0] & bank_mask;

    reg [1:0] half;                                 // address bits 2:1
    reg pend;
    always @(posedge clk) begin
        mem_req <= 1'b0; rvalid <= 1'b0;
        if (rst) pend <= 0;
        else begin
            if (rd && in_cart) begin
                mem_req  <= 1'b1;
                // 20-bit offset in the 1 MiB region, 4-byte aligned word
                mem_addr <= p_base
                          + (win ? ({24'd0, bank} + 32'd1) << 20 : 32'd0)
                          + {12'd0, ba[19:3], 3'b000};
                half <= ba[2:1];
                pend <= 1;
            end
            if (mem_valid && pend) begin
                pend   <= 0;
                rvalid <= 1'b1;
                case (half)
                2'd0: rdata <= {mem_rdata[7:0],   mem_rdata[15:8]};
                2'd1: rdata <= {mem_rdata[23:16], mem_rdata[31:24]};
                2'd2: rdata <= {mem_rdata[39:32], mem_rdata[47:40]};
                2'd3: rdata <= {mem_rdata[55:48], mem_rdata[63:56]};
                endcase
            end
        end
    end
endmodule
