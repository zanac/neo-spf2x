// System testbench: ng_top + ng_sdram + sim_sdr, commands from cmds.txt.
`timescale 1ns/1ps
module tb_top;
    reg clk = 0, rst = 1; always #5 clk = ~clk;           // 100 MHz
    reg [2:0] div = 0; reg tick12 = 0;
    always @(posedge clk) begin div <= (div == 7) ? 0 : div + 1; tick12 <= (div == 7); end

    reg pck1b = 0, pck2b = 0, ca4 = 0, load = 0, h = 0, s2h1 = 0; reg [23:0] pbus = 0;
    reg [22:0] p_a = 0; reg p_rd = 0, p_wr = 0; reg [15:0] p_wdata = 0;
    reg z_io_rd = 0, z_mrd = 0; reg [15:0] z_a = 0;
    reg v_rd = 0; reg [31:0] v_offs = 0;
    reg reg_wr = 0; reg [7:0] reg_addr = 0; reg [31:0] reg_wdata = 0;
    reg mcu_req = 0, mcu_we = 0; reg [31:0] mcu_addr = 0, mcu_wdata = 0;
    wire [3:0] gad, gbd; wire dota, dotb; wire [7:0] fixd; wire c_rdy0, c_rdy1, s_fvalid;
    wire [15:0] p_rdata; wire p_rvalid; wire [7:0] z_data, v_data; wire z_valid, v_valid;
    wire run, mcu_full, mcu_rvalid; wire [31:0] mcu_rdata;
    wire sd_cs_n, sd_ras_n, sd_cas_n, sd_we_n, sd_dq_oe; wire [1:0] sd_ba, sd_dqm;
    wire [12:0] sd_a; wire [15:0] sd_dq_o, sd_dq_i;

    wire [7:0] ar_ad_out, ap_ad_out; wire ar_drive, ap_drive; wire [15:0] ar_late, ap_late;
    ng_top dut(.ar_mpx(1'b0), .ar_oe_n(1'b1), .ar_ad_in(8'd0), .ar_a89(2'd0), .ar_a2023(4'd0),
        .ar_ad_out(ar_ad_out), .ar_drive(ar_drive), .ar_late(ar_late),
        .ap_mpx(1'b0), .ap_oe_n(1'b1), .ap_ad_in(8'd0), .ap_a811(4'd0),
        .ap_ad_out(ap_ad_out), .ap_drive(ap_drive), .ap_late(ap_late),.clk(clk), .rst(rst), .tick12(tick12), .pck1b(pck1b), .pck2b(pck2b),
        .ca4(ca4), .load(load), .h(h), .s2h1(s2h1), .pbus(pbus), .gad(gad), .gbd(gbd),
        .dota(dota), .dotb(dotb), .fixd(fixd), .c_rdy0(c_rdy0), .c_rdy1(c_rdy1),
        .s_fvalid(s_fvalid), .p_a(p_a), .p_rd(p_rd), .p_wr(p_wr), .p_wdata(p_wdata),
        .p_rdata(p_rdata), .p_rvalid(p_rvalid), .z_io_rd(z_io_rd), .z_mrd(z_mrd),
        .z_a(z_a), .z_data(z_data), .z_valid(z_valid), .v_rd(v_rd), .v_offs(v_offs),
        .v_data(v_data), .v_valid(v_valid), .reg_wr(reg_wr), .reg_addr(reg_addr),
        .reg_wdata(reg_wdata), .run(run), .mcu_req(mcu_req), .mcu_we(mcu_we),
        .mcu_addr(mcu_addr), .mcu_wdata(mcu_wdata), .mcu_full(mcu_full),
        .mcu_rvalid(mcu_rvalid), .mcu_rdata(mcu_rdata),
        .sd_cs_n(sd_cs_n), .sd_ras_n(sd_ras_n), .sd_cas_n(sd_cas_n), .sd_we_n(sd_we_n),
        .sd_ba(sd_ba), .sd_a(sd_a), .sd_dqm(sd_dqm), .sd_dq_o(sd_dq_o),
        .sd_dq_oe(sd_dq_oe), .sd_dq_i(sd_dq_i));
    wire [15:0] chip_dq;
    sim_sdr chip(.clk(clk), .cs_n(sd_cs_n), .ras_n(sd_ras_n), .cas_n(sd_cas_n),
        .we_n(sd_we_n), .ba(sd_ba), .a(sd_a), .dqm(sd_dqm), .dq_i(sd_dq_o),
        .dq_oe(sd_dq_oe), .dq_o(chip_dq));
    assign sd_dq_i = chip_dq;

    integer fv, fo, r, k, i; reg [31:0] op0; reg [31:0] x, y, zz;
    task tick; begin @(negedge clk); while (!tick12) @(negedge clk);
        @(posedge clk); #2; end endtask
    task wt(input integer n); integer j; begin for (j = 0; j < n; j = j + 1) tick; end endtask
    task clks(input integer n); begin repeat (n) @(posedge clk); #1; end endtask

    initial begin
        fv = $fopen("cmds.txt", "r"); fo = $fopen("out.txt", "w");
        repeat (4) @(posedge clk); #1 rst = 0;
        clks(600);                                          // SDRAM init
        while (!$feof(fv)) begin
            r = $fscanf(fv, "%s", op0);
            if (r == 1) case (op0)
            "R": begin r = $fscanf(fv, "%h %h\n", x, y);
                reg_addr = x; reg_wdata = y; reg_wr = 1; clks(1); reg_wr = 0; clks(1); end
            "MW": begin r = $fscanf(fv, "%h %h\n", x, y);
                mcu_addr = x; mcu_wdata = y; mcu_we = 1; mcu_req = 1; clks(1);
                mcu_req = 0; mcu_we = 0; k = 0;
                while (!mcu_rvalid && k < 200) begin clks(1); k = k + 1; end clks(1); end
            "MR": begin r = $fscanf(fv, "%h\n", x);
                mcu_addr = x; mcu_we = 0; mcu_req = 1; clks(1); mcu_req = 0; k = 0;
                while (!mcu_rvalid && k < 200) begin clks(1); k = k + 1; end
                $fwrite(fo, "MR %0h\n", mcu_rdata); clks(1); end
            "C": begin r = $fscanf(fv, "%h %h %d\n", x, y, zz);         // tile row h
                h = zz; pbus = {x[19:16], y[3:0], x[15:0]}; pck1b = 1; wt(4);
                for (i = 0; i < 2; i = i + 1) begin
                    ca4 = i; load = 1; tick; load = 0;
                    $fwrite(fo, "C %0d %0d %0d %0h %0h\n", i, zz, 0, gad, gbd);
                    for (k = 1; k < 4; k = k + 1) begin tick;
                        $fwrite(fo, "C %0d %0d %0d %0h %0h\n", i, zz, k, gad, gbd); end
                end
                pck1b = 0; wt(1); end
            "S": begin r = $fscanf(fv, "%h %h\n", x, y);                // tile pos
                pbus = {8'h00, y[3:0], x[11:0]}; pck2b = 1; clks(40);
                s2h1 = 0; #1 $fwrite(fo, "S %0h", fixd);
                s2h1 = 1; #1 $fwrite(fo, " %0h\n", fixd);
                pck2b = 0; clks(3); end
            "PR": begin r = $fscanf(fv, "%h\n", x);
                p_a = x[23:1]; p_rd = 1; clks(1); p_rd = 0; k = 0;
                while (!p_rvalid && k < 200) begin clks(1); k = k + 1; end
                $fwrite(fo, "PR %0h\n", p_rdata); clks(2); end
            "PW": begin r = $fscanf(fv, "%h %h\n", x, y);
                p_a = x[23:1]; p_wdata = y; p_wr = 1; clks(1); p_wr = 0; clks(2); end
            "ZP": begin r = $fscanf(fv, "%h\n", x);
                z_a = x; z_io_rd = 1; clks(1); z_io_rd = 0; clks(2); end
            "ZM": begin r = $fscanf(fv, "%h\n", x);
                z_a = x; clks(2); z_mrd = 1; clks(1); z_mrd = 0; k = 0;
                while (!z_valid && k < 200) begin clks(1); k = k + 1; end
                $fwrite(fo, "ZM %0h\n", z_data); clks(2); end
            "VR": begin r = $fscanf(fv, "%h\n", x);
                v_offs = x; v_rd = 1; clks(1); v_rd = 0; k = 0;
                while (!v_valid && k < 200) begin clks(1); k = k + 1; end
                $fwrite(fo, "VR %0h\n", v_data); clks(2); end
            endcase
        end
        $fwrite(fo, "SDRAM_ERRORS %0d READS %0d WRITES %0d REFRESH %0d\n",
                chip.errors, chip.nrd, chip.nwr, chip.nref);
        $fclose(fo); $finish;
    end
endmodule
