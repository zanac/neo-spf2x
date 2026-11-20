`timescale 1ns/1ps
module tb_sfetch;
    parameter LAT = 6;
    reg clk = 0, rst = 1; always #5 clk = ~clk;
    reg pck2b = 0; reg [23:0] pbus = 0; reg s2h1 = 0;
    wire [7:0] fixd; wire fvalid, mreq, mvalid; wire [31:0] maddr; wire [63:0] mdata;
    ng_sfetch dut(.s_base(32'h0), .clk(clk), .rst(rst), .pck2b(pck2b), .pbus(pbus),
        .s2h1(s2h1), .tile_mask(12'h03F), .fixd(fixd), .fvalid(fvalid),
        .mem_req(mreq), .mem_addr(maddr), .mem_valid(mvalid), .mem_rdata(mdata));
    sim_mem #(.LAT(LAT)) m(.clk(clk), .req(mreq), .addr(maddr), .valid(mvalid), .rdata(mdata));
    integer fv, fo, r, s, k; reg [11:0] tl; reg [3:0] pos; integer bad;
    initial begin
        fv = $fopen("vectors.txt", "r"); fo = $fopen("out.txt", "w"); bad = 0;
        repeat (4) @(posedge clk); rst = 0; repeat (2) @(posedge clk); #1;
        while (!$feof(fv)) begin
            r = $fscanf(fv, "%h %h\n", tl, pos);
            if (r == 2) begin
                pbus = {8'h00, pos, tl}; pck2b = 1; repeat (2) @(posedge clk); #1;
                k = 0; while (!fvalid && k < 100) begin @(posedge clk); #1; k = k + 1; end
                if (k >= 100) bad = bad + 1;
                #1;
                for (s = 0; s < 2; s = s + 1) begin
                    s2h1 = s[0]; #1; $fwrite(fo, "%0d %0d %0h\n", k, s, fixd);
                end
                pck2b = 0; repeat (3) @(posedge clk); #1;
            end
        end
        $fwrite(fo, "TIMEOUT %0d\n", bad); $fclose(fo); $finish;
    end
endmodule
