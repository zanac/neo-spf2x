`timescale 1ns/1ps
module tb_pbank;
    parameter LAT = 6;
    reg clk = 0, rst = 1; always #5 clk = ~clk;
    reg [22:0] a = 0; reg rd = 0, wr = 0; reg [15:0] wd = 0;
    wire [15:0] rdata; wire rvalid, in_cart, mreq, mvalid; wire [31:0] maddr; wire [63:0] mdata;
    ng_pbank dut(.p_base(32'h0), .clk(clk), .rst(rst), .bank_mask(8'h03), .a(a), .rd(rd),
        .wr(wr), .wdata(wd), .rdata(rdata), .rvalid(rvalid), .in_cart(in_cart),
        .mem_req(mreq), .mem_addr(maddr), .mem_valid(mvalid), .mem_rdata(mdata));
    sim_mem #(.LAT(LAT), .NWORDS(1572864)) m(.clk(clk), .req(mreq), .addr(maddr),
        .valid(mvalid), .rdata(mdata));
    integer fv, fo, r, k; reg [7:0] op; reg [23:0] ad; reg [15:0] dv;
    initial begin
        fv = $fopen("vectors.txt", "r"); fo = $fopen("out.txt", "w");
        repeat (4) @(posedge clk); rst = 0; repeat (2) @(posedge clk); #1;
        while (!$feof(fv)) begin
            r = $fscanf(fv, "%c %h %h\n", op, ad, dv);
            if (r == 3) begin
                a = ad[23:1]; wd = dv;
                if (op == "W") begin wr = 1; @(posedge clk); #1 wr = 0; end
                else begin
                    rd = 1; @(posedge clk); #1 rd = 0;
                    k = 0; while (!rvalid && k < 100) begin @(posedge clk); #1 k = k + 1; end
                    $fwrite(fo, "%0h %0d\n", rdata, in_cart);
                end
                repeat (2) @(posedge clk); #1;
            end
        end
        $fclose(fo); $finish;
    end
endmodule
