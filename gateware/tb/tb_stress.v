// Stress testbench: worst-case concurrent traffic (docs/GATEWARE.md) on the RTL
// chain ng_top + ng_sdram + sim_sdr.  Reports request->ready latency per class.
`timescale 1ns/1ps
module tb_stress;
    parameter real PERIOD = 10.4167;     // ns, clock period
    parameter DIV12 = 8;                 // clk cycles per 12M period
    parameter TRCD = 2, CL = 3, TRC = 7, TRP = 2, TRFC = 7, TWR = 2, REFI = 740;
    parameter NS_SIM = 2000000;          // simulated time after start (ns)
    reg clk = 0, rst = 1; always #(PERIOD/2.0) clk = ~clk;
    integer div = 0; reg tick12 = 0;
    always @(posedge clk) begin div <= (div == DIV12-1) ? 0 : div + 1; tick12 <= (div == DIV12-1); end

    reg pck1b = 0, pck2b = 0, ca4 = 0, load = 0, h = 0, s2h1 = 0; reg [23:0] pbus = 0;
    reg [22:0] p_a = 0; reg p_rd = 0; reg z_io_rd = 0, z_mrd = 0; reg [15:0] z_a = 0;
    reg v_rd = 0; reg [31:0] v_offs = 0;
    reg reg_wr = 0; reg [7:0] reg_addr = 0; reg [31:0] reg_wdata = 0;
    wire [3:0] gad, gbd; wire dota, dotb; wire [7:0] fixd; wire c_rdy0, c_rdy1, s_fvalid;
    wire [15:0] p_rdata; wire p_rvalid; wire [7:0] z_data, v_data; wire z_valid, v_valid;
    wire [1:0] sd_cs_n; wire sd_ras_n, sd_cas_n, sd_we_n, sd_dq_oe; wire [1:0] sd_ba, sd_dqm;
    wire [12:0] sd_a; wire [15:0] sd_dq_o, chip_dq;

    wire [7:0] ar_ad_out, ap_ad_out; wire ar_drive, ap_drive; wire [15:0] ar_late, ap_late;
    ng_top dut(.ar_mpx(1'b0), .ar_oe_n(1'b1), .ar_ad_in(8'd0), .ar_a89(2'd0), .ar_a2023(4'd0),
        .ar_ad_out(ar_ad_out), .ar_drive(ar_drive), .ar_late(ar_late),
        .ap_mpx(1'b0), .ap_oe_n(1'b1), .ap_ad_in(8'd0), .ap_a811(4'd0),
        .ap_ad_out(ap_ad_out), .ap_drive(ap_drive), .ap_late(ap_late),.clk(clk), .rst(rst), .tick12(tick12), .pck1b(pck1b), .pck2b(pck2b),
        .ca4(ca4), .load(load), .h(h), .s2h1(s2h1), .pbus(pbus), .gad(gad), .gbd(gbd),
        .dota(dota), .dotb(dotb), .fixd(fixd), .c_rdy0(c_rdy0), .c_rdy1(c_rdy1),
        .s_fvalid(s_fvalid), .p_a(p_a), .p_rd(p_rd), .p_wr(1'b0), .p_wdata(16'h0),
        .p_rdata(p_rdata), .p_rvalid(p_rvalid), .z_io_rd(z_io_rd), .z_mrd(z_mrd),
        .z_a(z_a), .z_data(z_data), .z_valid(z_valid), .v_rd(v_rd), .v_offs(v_offs),
        .v_data(v_data), .v_valid(v_valid), .reg_wr(reg_wr), .reg_addr(reg_addr),
        .reg_wdata(reg_wdata), .run(), .mcu_req(1'b0), .mcu_we(1'b0),
        .mcu_addr(32'h0), .mcu_wdata(32'h0), .mcu_full(), .mcu_rvalid(), .mcu_rdata(),
        .sd_cs_n(sd_cs_n), .sd_ras_n(sd_ras_n), .sd_cas_n(sd_cas_n), .sd_we_n(sd_we_n),
        .sd_ba(sd_ba), .sd_a(sd_a), .sd_dqm(sd_dqm), .sd_dq_o(sd_dq_o),
        .sd_dq_oe(sd_dq_oe), .sd_dq_i(chip_dq));
    sim_sdr #(.TRCD(TRCD), .TRC(TRC), .TRP(TRP), .TRFC(TRFC), .REFI(REFI), .CL(CL))
        chip(.clk(clk), .cs_n(sd_cs_n[0]), .ras_n(sd_ras_n), .cas_n(sd_cas_n),
        .we_n(sd_we_n), .ba(sd_ba), .a(sd_a), .dqm(sd_dqm), .dq_i(sd_dq_o),
        .dq_oe(sd_dq_oe), .dq_o(chip_dq));
    defparam dut.sdr.TRCD = TRCD, dut.sdr.CL = CL, dut.sdr.TRC = TRC,
             dut.sdr.TRP = TRP, dut.sdr.TRFC = TRFC, dut.sdr.TWR = TWR,
             dut.sdr.REFI = REFI;

    task regw(input [7:0] a, input [31:0] d); begin
        reg_addr = a; reg_wdata = d; reg_wr = 1; @(posedge clk); #1 reg_wr = 0; @(posedge clk); #1;
    end endtask

    function integer cyc(input integer ns); cyc = (ns * 1.0 / PERIOD) + 0.5; endfunction
    integer PC, PS, PP, PM, PV, n, seed;
    // latency tracking (in clk cycles)
    integer t0c, t0s, t0p, t0m, t0v; reg wc0, wc1, ws, wp, wm, wv;
    integer maxc0, maxc1, maxs, maxp, maxm, maxv, nc, ns_, np, nm, nv;
    integer sumc1;
    reg [23:0] paddr; integer started;

    initial begin
        seed = 7; n = 0; started = 0;
        maxc0 = 0; maxc1 = 0; maxs = 0; maxp = 0; maxm = 0; maxv = 0;
        nc = 0; ns_ = 0; np = 0; nm = 0; nv = 0; sumc1 = 0;
        wc0 = 0; wc1 = 0; ws = 0; wp = 0; wm = 0; wv = 0; paddr = 0;
        PC = cyc(667); PS = cyc(667); PP = cyc(333); PM = cyc(750); PV = cyc(12000);
        repeat (4) @(posedge clk); #1 rst = 0;
        repeat (800) @(posedge clk); #1;
        regw(8'h10, 32'h300000); regw(8'h20, 32'h0);          // P 3 MiB @0
        regw(8'h11, 32'h40000);  regw(8'h21, 32'h400000);     // C 256 KiB
        regw(8'h12, 32'h10000);  regw(8'h22, 32'h340000);     // S 64 KiB
        regw(8'h13, 32'h40000);  regw(8'h23, 32'h350000);     // M 256 KiB
        regw(8'h14, 32'h20000);  regw(8'h24, 32'h300000);     // V 128 KiB
        regw(8'h00, 32'h1);
        started = 1;
        while (n < NS_SIM / PERIOD) begin
            @(posedge clk); #1; n = n + 1;
            if (n % PC == 0) begin pbus = 24'd0; pbus[15:0] = $urandom; pbus[19:16] = $urandom;
                pck1b = 1; t0c = n; wc0 = 1; wc1 = 1; end
            if (n % PC == 8) pck1b = 0;
            if (n % PS == 25) begin pbus = $urandom % 4096 | (($urandom % 16) << 12);
                pck2b = 1; t0s = n; ws = 1; end
            if (n % PS == 33) pck2b = 0;
            if (n % PP == 3) begin p_a = (paddr >> 1) % 23'h80000; paddr = paddr + 2; p_rd = 1; t0p = n; wp = 1; end
            else p_rd = 0;
            if (n % PM == 5) begin z_a = $urandom % 16'hF800; end
            if (n % PM == 8) begin z_mrd = 1; t0m = n; wm = 1; end else z_mrd = 0;
            if (n % PV == 11) begin v_offs = $urandom % 32'h20000; v_rd = 1; t0v = n; wv = 1; end else v_rd = 0;
            // completion monitors (skip the 3 cycles the modules need to clear flags)
            if (wc0 && n - t0c > 3 && c_rdy0) begin wc0 = 0;
                if (n - t0c > maxc0) maxc0 = n - t0c; end
            if (wc1 && n - t0c > 3 && c_rdy1) begin wc1 = 0; nc = nc + 1; sumc1 = sumc1 + n - t0c;
                if (n - t0c > maxc1) maxc1 = n - t0c; end
            if (ws && n - t0s > 3 && s_fvalid) begin ws = 0; ns_ = ns_ + 1;
                if (n - t0s > maxs) maxs = n - t0s; end
            if (wp && p_rvalid) begin wp = 0; np = np + 1; if (n - t0p > maxp) maxp = n - t0p; end
            if (wm && z_valid) begin wm = 0; nm = nm + 1; if (n - t0m > maxm) maxm = n - t0m; end
            if (wv && v_valid) begin wv = 0; nv = nv + 1; if (n - t0v > maxv) maxv = n - t0v; end
        end
        $display("PERIOD %f", PERIOD);
        $display("C_HALF0_MAX %f", maxc0 * PERIOD);
        $display("C_ROW_MAX %f", maxc1 * PERIOD);
        $display("C_ROW_AVG %f", (sumc1 * 1.0 / nc) * PERIOD);
        $display("S_MAX %f", maxs * PERIOD);
        $display("P_MAX %f", maxp * PERIOD);
        $display("M_MAX %f", maxm * PERIOD);
        $display("V_MAX %f", maxv * PERIOD);
        $display("EVENTS C %0d S %0d P %0d M %0d V %0d", nc, ns_, np, nm, nv);
        $display("SDRAM_ERRORS %0d READS %0d REFRESH %0d", chip.errors, chip.nrd, chip.nref);
        $finish;
    end
endmodule
