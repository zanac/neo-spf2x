// Testbench for ng_cfetch_mvs and ng_mvs_pdec.  Self-checking, prints
// "TB_MVS PASS" or "TB_MVS FAIL n".
`timescale 1ns/1ps
module tb_mvs;
    parameter LAT = 6;
    reg clk = 0, rst = 1;
    always #5 clk = ~clk;
    reg pck1b = 0, ca4 = 0; reg [23:0] pbus = 0;
    wire [31:0] cr; wire ready, mem_req; wire [31:0] mem_addr;
    reg mem_valid = 0; reg [63:0] mem_rdata = 0;
    ng_cfetch_mvs dut(.clk(clk), .rst(rst), .pck1b(pck1b), .pbus(pbus), .ca4(ca4),
        .tile_mask(20'h000FF), .c_base(32'h0), .cr(cr), .ready(ready),
        .mem_req(mem_req), .mem_addr(mem_addr), .mem_valid(mem_valid),
        .mem_rdata(mem_rdata));

    reg [31:0] mem [0:4095];
    reg [63:0] pd [0:15]; reg pv [0:15];
    integer i;
    always @(posedge clk) begin
        for (i = 15; i > 0; i = i - 1) begin pd[i] <= pd[i-1]; pv[i] <= pv[i-1]; end
        pv[0] <= mem_req;
        pd[0] <= {mem[((mem_addr[31:3] << 1) + 1) % 4096], mem[(mem_addr[31:3] << 1) % 4096]};
        mem_valid <= pv[LAT-1]; mem_rdata <= pd[LAT-1];
    end

    // ---- pdec ----
    reg [19:1] a = 0; reg roU = 1, roL = 1, poU = 1, poL = 1, pwU = 1, pwL = 1;
    wire [22:0] p_a; wire p_rd, p_wr;
    ng_mvs_pdec pd_(.clk(clk), .rst(rst), .a(a), .romoeu_n(roU), .romoel_n(roL),
        .portoeu_n(poU), .portoel_n(poL), .portweu_n(pwU), .portwel_n(pwL),
        .p_a(p_a), .p_rd(p_rd), .p_wr(p_wr));
    reg rd_seen, wr_seen; reg [22:0] a_rd, a_wr;
    always @(posedge clk) begin
        if (p_rd) begin rd_seen <= 1; a_rd <= p_a; end
        if (p_wr) begin wr_seen <= 1; a_wr <= p_a; end
    end

    integer errs = 0, n, t, row;
    reg [31:0] e0, e1;
    initial begin
        for (n = 0; n < 4096; n = n + 1) mem[n] = $random;
        repeat (4) @(posedge clk); rst = 0; repeat (4) @(posedge clk);
        for (n = 0; n < 40; n = n + 1) begin
            t = $random & 255; row = $random & 15;
            pbus = 24'd0;
            pbus[15:0] = {8'd0, t[7:0]}; pbus[19:16] = row; pbus[23:20] = 0;
            e0 = mem[((t * 128 + row * 8) / 4) % 4096];
            e1 = mem[((t * 128 + row * 8) / 4 + 1) % 4096];
            ca4 = 0;
            @(posedge clk); #1 pck1b = 1; repeat (3) @(posedge clk); #1 pck1b = 0;
            repeat (20) @(posedge clk);
            #1;
            if (!ready || cr !== e0) begin errs = errs + 1; $display("C0 mismatch t=%0d row=%0d %h/%h", t, row, cr, e0); end
            ca4 = 1; #1;
            if (cr !== e1) begin errs = errs + 1; $display("C1 mismatch t=%0d row=%0d %h/%h", t, row, cr, e1); end
        end
        // pdec: ROMOEL read at A=0x12345 -> word address 0x012345
        a = 19'h12345; @(posedge clk); #1 roL = 0; repeat (6) @(posedge clk); #1 roL = 1;
        repeat (4) @(posedge clk);
        if (!rd_seen || a_rd !== {4'h0, 19'h12345}) begin errs = errs + 1; $display("pdec ROM %h", a_rd); end
        rd_seen = 0;
        a = 19'h00044; poU = 0; repeat (6) @(posedge clk); #1 poU = 1;
        repeat (4) @(posedge clk);
        if (!rd_seen || a_rd !== {4'h2, 19'h00044}) begin errs = errs + 1; $display("pdec PORT %h", a_rd); end
        a = 19'h7FFF8; pwL = 0; repeat (6) @(posedge clk); #1 pwL = 1;
        repeat (4) @(posedge clk);
        if (!wr_seen || a_wr !== {4'h2, 19'h7FFF8}) begin errs = errs + 1; $display("pdec WR %h", a_wr); end
        if (errs == 0) $display("TB_MVS PASS"); else $display("TB_MVS FAIL %0d", errs);
        $finish;
    end
endmodule
