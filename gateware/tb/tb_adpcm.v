// Testbench: ng_adpcm (A and B) + ng_rdport + a fixed-latency memory.  Self-checking.
// Prints "TB_ADPCM PASS" or "TB_ADPCM FAIL n".
`timescale 1ns/1ps
module tb_adpcm;
    parameter LAT = 12;               // memory latency in clk cycles (100 MHz)
    reg clk = 0, rst = 1; always #5 clk = ~clk;

    // bus A
    reg a_mpx = 0, a_oe_n = 1; reg [7:0] a_in = 0; reg [1:0] a_a89 = 0; reg [3:0] a_top = 0;
    wire [7:0] a_out; wire a_drv; wire a_rd; wire [31:0] a_off; wire [15:0] a_late;
    wire [7:0] a_dat; wire a_val; wire a_mreq; wire [31:0] a_ma;
    // bus B
    reg b_mpx = 0, b_oe_n = 1; reg [7:0] b_in = 0; reg [3:0] b_a = 0;
    wire [7:0] b_out; wire b_drv; wire b_rd; wire [31:0] b_off; wire [15:0] b_late;
    wire [7:0] b_dat; wire b_val; wire b_mreq; wire [31:0] b_ma;

    ng_adpcm #(.B(0)) A(.clk(clk), .rst(rst), .mpx(a_mpx), .oe_n(a_oe_n), .ad_in(a_in),
        .a_mid({2'b00, a_a89}), .a_top(a_top), .ad_out(a_out), .ad_drive(a_drv),
        .rd(a_rd), .offs(a_off), .rdata(a_dat), .rvalid(a_val), .late(a_late));
    ng_adpcm #(.B(1)) Bq(.clk(clk), .rst(rst), .mpx(b_mpx), .oe_n(b_oe_n), .ad_in(b_in),
        .a_mid(b_a), .a_top(4'd0), .ad_out(b_out), .ad_drive(b_drv),
        .rd(b_rd), .offs(b_off), .rdata(b_dat), .rvalid(b_val), .late(b_late));

    // memory: 2^22 bytes visible (address bits above are folded), word = 8 bytes
    reg [7:0] mem [0:4194303];
    reg [63:0] pa [0:31]; reg pva [0:31]; reg [63:0] pb [0:31]; reg pvb [0:31];
    wire [63:0] a_w = {mem[{a_ma[21:3],3'd7}], mem[{a_ma[21:3],3'd6}], mem[{a_ma[21:3],3'd5}], mem[{a_ma[21:3],3'd4}],
                       mem[{a_ma[21:3],3'd3}], mem[{a_ma[21:3],3'd2}], mem[{a_ma[21:3],3'd1}], mem[{a_ma[21:3],3'd0}]};
    wire [63:0] b_w = {mem[{b_ma[21:3],3'd7}], mem[{b_ma[21:3],3'd6}], mem[{b_ma[21:3],3'd5}], mem[{b_ma[21:3],3'd4}],
                       mem[{b_ma[21:3],3'd3}], mem[{b_ma[21:3],3'd2}], mem[{b_ma[21:3],3'd1}], mem[{b_ma[21:3],3'd0}]};
    integer i;
    reg a_mv = 0, b_mv = 0; reg [63:0] a_md = 0, b_md = 0;
    always @(posedge clk) begin
        for (i = 31; i > 0; i = i - 1) begin
            pa[i] <= pa[i-1]; pva[i] <= pva[i-1]; pb[i] <= pb[i-1]; pvb[i] <= pvb[i-1];
        end
        pva[0] <= a_mreq; pa[0] <= a_w; pvb[0] <= b_mreq; pb[0] <= b_w;
        a_mv <= pva[LAT-1]; a_md <= pa[LAT-1]; b_mv <= pvb[LAT-1]; b_md <= pb[LAT-1];
    end
    ng_rdport ra(.clk(clk), .rst(rst), .rd(a_rd), .offs(a_off), .base(32'd0), .mem_req(a_mreq),
        .mem_addr(a_ma), .mem_valid(a_mv), .mem_rdata(a_md), .data(a_dat), .valid(a_val));
    ng_rdport rb(.clk(clk), .rst(rst), .rd(b_rd), .offs(b_off), .base(32'd0), .mem_req(b_mreq),
        .mem_addr(b_ma), .mem_valid(b_mv), .mem_rdata(b_md), .data(b_dat), .valid(b_val));

    reg [31:0] la = 0, lb = 0;
    always @(posedge clk) begin if (a_rd) la <= a_off; if (b_rd) lb <= b_off; end
    integer errs = 0, n, k; reg [23:0] ad; reg [7:0] exp, got;
    localparam TA = 1500, TB = 250;           // period lengths (ns) of bus A / bus B

    task read_a(input [23:0] adr);            // ADPCM-A cycle
        begin
            a_in = adr[7:0]; a_a89 = adr[9:8]; a_top = adr[23:20];
            #(TA) a_mpx = 1;
            #(TA) a_in = adr[17:10]; a_a89 = adr[19:18];
            #(TA) a_mpx = 0;
            #(TA) a_oe_n = 0;
            #(TA) got = a_drv ? a_out : 8'hxx; a_oe_n = 1;
        end
    endtask
    task read_b(input [23:0] adr);            // ADPCM-B cycle
        begin
            b_in = adr[7:0]; b_a = adr[11:8];
            #(TB) b_mpx = 1;
            #(TB) b_in = adr[19:12]; b_a = adr[23:20];
            #(TB) b_mpx = 0;
            #(TB) b_oe_n = 0;
            #(TB) got = b_drv ? b_out : 8'hxx; b_oe_n = 1;
        end
    endtask

    initial begin
        for (n = 0; n < 4194304; n = n + 1) mem[n] = $random;
        repeat (4) @(posedge clk); #1 rst = 0; repeat (4) @(posedge clk);
        for (k = 0; k < 40; k = k + 1) begin
            ad = $random;                                   // full 24 bits (memory model folds)
            exp = mem[ad[21:0]];
            read_a(ad);
            if (la !== {8'd0, ad}) begin errs = errs + 1; $display("A addr %h vs %h", la, ad); end
            if (got !== exp) begin errs = errs + 1; $display("A %h: got %h exp %h", ad, got, exp); end
            ad = $random;
            exp = mem[ad[21:0]];
            read_b(ad);
            if (lb !== {8'd0, ad}) begin errs = errs + 1; $display("B addr %h vs %h", lb, ad); end
            if (got !== exp) begin errs = errs + 1; $display("B %h: got %h exp %h", ad, got, exp); end
        end
        if (a_late != 0 || b_late != 0) begin errs = errs + 1; $display("late a=%0d b=%0d", a_late, b_late); end
        // full 24-bit addressing check on the decoded request (no data check)
        if (errs == 0) $display("TB_ADPCM PASS"); else $display("TB_ADPCM FAIL %0d", errs);
        $finish;
    end
endmodule
