// Testbench: drives vectors from vectors.txt, SDRAM image from sdram.hex.
// vectors.txt lines: tile(hex 6) row(hex 1) h(0/1)
// Output (out.txt): per vector 8 pairs "gad gbd" for half0 then half1, i.e.
// 16 lines of the form  half tick gad gbd, plus ready-latency stats.
`timescale 1ns/1ps
module tb_cfetch;
    parameter LAT = 6;            // SDRAM read latency in clk cycles
    parameter LOAD_DELAY = 3;     // 12M ticks from PCK1B rise to first LOAD
    parameter NWORDS = 65536;
    parameter MASK = 20'h0003F;
    reg clk = 0, rst = 1;
    always #5 clk = ~clk;         // 100 MHz
    reg [2:0] div = 0;
    reg tick12 = 0;
    always @(posedge clk) begin div <= (div == 3'd7) ? 0 : div + 1;
                                tick12 <= (div == 3'd7); end

    reg pck1b = 0; reg [23:0] pbus = 0; reg ca4 = 0, load = 0, h = 0;
    wire [3:0] gad, gbd; wire dota, dotb, mem_req, rdy0, rdy1;
    wire [31:0] mem_addr; reg mem_valid = 0; reg [63:0] mem_rdata = 0;

    ng_cfetch dut(.c_base(32'h0), .clk(clk), .rst(rst), .tick12(tick12),
        .pck1b(pck1b), .pbus(pbus), .ca4(ca4), .load(load), .h(h),
        .tile_mask(MASK[19:0]), .gad(gad), .gbd(gbd), .dota(dota), .dotb(dotb),
        .mem_req(mem_req), .mem_addr(mem_addr), .mem_valid(mem_valid),
        .mem_rdata(mem_rdata), .rdy0(rdy0), .rdy1(rdy1));


    reg [31:0] mem [0:NWORDS-1];
    // read pipeline with fixed latency
    reg [63:0] pipe_d [0:15]; reg pipe_v [0:15];
    integer i;
    always @(posedge clk) begin
        for (i = 15; i > 0; i = i - 1) begin
            pipe_d[i] <= pipe_d[i-1]; pipe_v[i] <= pipe_v[i-1];
        end
        pipe_v[0] <= mem_req;
        pipe_d[0] <= {mem[((mem_addr[31:3] << 1) + 1) % NWORDS], mem[(mem_addr[31:3] << 1) % NWORDS]};
        mem_valid <= pipe_v[LAT-1];
        mem_rdata <= pipe_d[LAT-1];
    end

    integer fv, fo, r, half, k, underrun;
    reg [23:0] tl; reg [3:0] rw; reg hv;
    // wait for a tick12 pulse; the DUT consumes it at the next posedge
    task tick; begin
        @(negedge clk); while (!tick12) @(negedge clk);
        @(posedge clk); #2;
    end endtask
    task wait_ticks(input integer n_); integer j; begin
        for (j = 0; j < n_; j = j + 1) tick; end endtask

    initial begin
        $readmemh("sdram.hex", mem);
        fv = $fopen("vectors.txt", "r");
        fo = $fopen("out.txt", "w");
        underrun = 0;
        repeat (4) @(posedge clk); rst = 0; repeat (4) @(posedge clk);
        while (!$feof(fv)) begin
            r = $fscanf(fv, "%h %h %d\n", tl, rw, hv);
            if (r == 3) begin
                h = hv;
                pbus = {tl[19:16], rw, tl[15:0]};
                pck1b = 1;
                wait_ticks(LOAD_DELAY);
                for (half = 0; half < 2; half = half + 1) begin
                    ca4 = half[0];
                    load = 1;
                    if (!(ca4 ? rdy1 : rdy0)) underrun = underrun + 1;
                    tick;                      // load happens on this tick
                    load = 0;
                    $fwrite(fo, "%0d %0d %0d %0d %0d\n", half, hv, 0, gad, gbd);
                    for (k = 1; k < 4; k = k + 1) begin
                        tick;
                        $fwrite(fo, "%0d %0d %0d %0d %0d\n", half, hv, k, gad, gbd);
                    end
                end
                pck1b = 0;
                wait_ticks(1);
            end
        end
        $fwrite(fo, "UNDERRUN %0d\n", underrun);
        $fclose(fo); $finish;
    end
endmodule
