// Two SDRAM chips on one bus (ngsd-128M): chip select by addr[26]; init/refresh on both.
`timescale 1ns/1ps
module tb_sdram2;
    reg clk = 0, rst = 1;
    always #3.5 clk = ~clk;
    reg req_valid = 0, req_we = 0; reg [31:0] req_addr = 0, req_wdata = 0;
    wire req_ready, rsp_valid; wire [63:0] rsp_rdata;
    wire [1:0] cs_n; wire ras_n, cas_n, we_n; wire [1:0] ba, dqm; wire [12:0] a;
    wire [15:0] dq_o; wire dq_oe; wire [15:0] dq0, dq1;
    wire [15:0] dq_i = (dq0 !== 16'hzzzz) ? dq0 : dq1;
    ng_sdram #(.INIT_CLKS(64)) dut(.clk(clk), .rst(rst), .req_valid(req_valid), .req_we(req_we),
        .req_addr(req_addr), .req_wdata(req_wdata), .req_ready(req_ready), .rsp_valid(rsp_valid),
        .rsp_rdata(rsp_rdata), .sd_cs_n(cs_n), .sd_ras_n(ras_n), .sd_cas_n(cas_n), .sd_we_n(we_n),
        .sd_ba(ba), .sd_a(a), .sd_dqm(dqm), .sd_dq_o(dq_o), .sd_dq_oe(dq_oe), .sd_dq_i(dq_i));
    sim_sdr c0(.clk(clk), .cs_n(cs_n[0]), .ras_n(ras_n), .cas_n(cas_n), .we_n(we_n), .ba(ba), .a(a),
        .dqm(dqm), .dq_i(dq_o), .dq_oe(dq_oe), .dq_o(dq0));
    sim_sdr c1(.clk(clk), .cs_n(cs_n[1]), .ras_n(ras_n), .cas_n(cas_n), .we_n(we_n), .ba(ba), .a(a),
        .dqm(dqm), .dq_i(dq_o), .dq_oe(dq_oe), .dq_o(dq1));
    integer bad = 0;
    task xfer(input we, input [31:0] ad, input [31:0] wd);
        begin
            @(posedge clk); while (!req_ready) @(posedge clk);
            req_valid <= 1; req_we <= we; req_addr <= ad; req_wdata <= wd;
            @(posedge clk); while (!req_ready) @(posedge clk);
            req_valid <= 0;
            @(posedge clk); while (!rsp_valid) @(posedge clk);
        end
    endtask
    task rd(input [31:0] ad, input [31:0] lo, input [31:0] hi, input [255:0] tag);
        begin
            xfer(0, ad, 0);
            if (rsp_rdata !== {hi, lo}) begin
                bad = bad + 1; $display("MISMATCH %0s: %h expected %h", tag, rsp_rdata, {hi, lo});
            end
        end
    endtask
    integer i;
    initial begin
        for (i = 0; i < 4; i = i + 1) @(posedge clk);
        rst <= 0;
        repeat (400) @(posedge clk);
        xfer(1, 32'h0000_0100, 32'hA0A1_A2A3);
        xfer(1, 32'h0000_0104, 32'hA4A5_A6A7);
        xfer(1, 32'h0400_0100, 32'hB0B1_B2B3);
        xfer(1, 32'h0400_0104, 32'hB4B5_B6B7);
        rd(32'h0000_0100, 32'hA0A1_A2A3, 32'hA4A5_A6A7, "chip0");
        rd(32'h0400_0100, 32'hB0B1_B2B3, 32'hB4B5_B6B7, "chip1");
        repeat (3000) @(posedge clk);               // several refreshes, both chips
        rd(32'h0000_0100, 32'hA0A1_A2A3, 32'hA4A5_A6A7, "chip0 again");
        rd(32'h0400_0100, 32'hB0B1_B2B3, 32'hB4B5_B6B7, "chip1 again");
        $display("SDRAM2 errors0=%0d errors1=%0d bad=%0d ref0=%0d ref1=%0d rd0=%0d rd1=%0d",
                 c0.errors, c1.errors, bad, c0.nref, c1.nref, c0.nrd, c1.nrd);
        $finish;
    end
endmodule
