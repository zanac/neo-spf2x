`timescale 1ns/1ps
module tb_zmc;
    reg clk = 0, rst = 1; always #5 clk = ~clk;
    reg io_rd = 0; reg [15:0] za = 0; wire [18:0] m_addr; wire m_sel;
    ng_zmc dut(.clk(clk), .rst(rst), .io_rd(io_rd), .za(za), .m_addr(m_addr), .m_sel(m_sel));
    integer fv, fo, r; reg [7:0] op; reg [15:0] av;
    initial begin
        fv = $fopen("vectors.txt", "r"); fo = $fopen("out.txt", "w");
        repeat (3) @(posedge clk); #1 rst = 0;
        while (!$feof(fv)) begin
            r = $fscanf(fv, "%c %h\n", op, av);
            if (r == 2) begin
                za = av;
                if (op == "P") begin io_rd = 1; @(posedge clk); #1 io_rd = 0; end
                else begin #2 $fwrite(fo, "%0h %0d\n", m_addr, m_sel); end
                @(posedge clk); #1;
            end
        end
        $fclose(fo); $finish;
    end
endmodule
