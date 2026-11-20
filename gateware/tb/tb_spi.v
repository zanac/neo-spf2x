// Testbench for ng_mcu_spi with a behavioural word memory.  Self-checking.
`timescale 1ns/1ps
module tb_spi;
    reg clk = 0, rst = 1; always #5 clk = ~clk;                 // 100 MHz
    integer HR = 40;        // half-period ns: 20 for writes (25 MHz), 40 for reads (12.5 MHz)
    reg sclk = 0, cs_n = 1, mosi = 0, io1 = 0, io2 = 0, io3 = 0; wire miso, miso_oe;
    wire reg_wr; wire [7:0] reg_addr; wire [31:0] reg_wdata;
    wire mcu_req, mcu_we; wire [31:0] mcu_addr, mcu_wdata;
    reg mcu_rvalid = 0; reg [31:0] mcu_rdata = 0;
    reg full = 0;
    ng_mcu_spi dut(.clk(clk), .rst(rst), .sclk(sclk), .cs_n(cs_n), .mosi(mosi), .io1_in(io1), .io2_in(io2), .io3_in(io3), .miso(miso),
        .miso_oe(miso_oe), .reg_wr(reg_wr), .reg_addr(reg_addr), .reg_wdata(reg_wdata),
        .run(1'b1), .mcu_req(mcu_req), .mcu_we(mcu_we), .mcu_addr(mcu_addr),
        .mcu_wdata(mcu_wdata), .mcu_full(full), .mcu_rvalid(mcu_rvalid), .mcu_rdata(mcu_rdata));

    reg [31:0] mem [0:1023];
    reg [31:0] rd_pipe0, rd_pipe1, rd_pipe2; reg v0, v1, v2;
    always @(posedge clk) begin
        mcu_rvalid <= v2; mcu_rdata <= rd_pipe2;
        v2 <= v1; rd_pipe2 <= rd_pipe1; v1 <= v0; rd_pipe1 <= rd_pipe0;
        v0 <= 0;
        if (mcu_req) begin
            if (mcu_we) mem[mcu_addr[11:2]] <= mcu_wdata;
            else begin v0 <= 1; rd_pipe0 <= mem[mcu_addr[11:2]]; end
        end
    end
    reg [7:0] r_addr = 0; reg [31:0] r_data = 0; reg r_seen = 0;
    always @(posedge clk) if (reg_wr) begin r_addr <= reg_addr; r_data <= reg_wdata; r_seen <= 1; end

    task sbyte(input [7:0] b); integer i; begin
        for (i = 7; i >= 0; i = i - 1) begin mosi = b[i]; #HR sclk = 1; #HR sclk = 0; end end endtask
    task qnib(input [3:0] n); begin
        {io3, io2, io1, mosi} = n; #HR sclk = 1; #HR sclk = 0; end endtask
    task qword(input [31:0] w); integer i; begin
        for (i = 7; i >= 0; i = i - 1) qnib(w[4*i +: 4]); end endtask
    task sword(input [31:0] w); begin sbyte(w[31:24]); sbyte(w[23:16]); sbyte(w[15:8]); sbyte(w[7:0]); end endtask
    reg [31:0] rx;
    task rbits(input integer n); integer i; begin
        rx = 0; for (i = 0; i < n; i = i + 1) begin mosi = 0; #HR sclk = 1; rx = {rx[30:0], miso}; #HR sclk = 0; end end endtask
    task start; begin #50 cs_n = 0; #50; end endtask
    task stop;  begin #50 cs_n = 1; #100; end endtask

    integer errs = 0, k;
    initial begin
        for (k = 0; k < 1024; k = k + 1) mem[k] = 0;
        repeat (4) @(posedge clk); rst = 0; repeat (4) @(posedge clk);
        // register write
        HR = 20;
        start; sbyte(8'h01); sbyte(8'h22); sword(32'hCAFEF00D); stop;
        if (!r_seen || r_addr !== 8'h22 || r_data !== 32'hCAFEF00D) begin errs = errs + 1; $display("REG %h %h", r_addr, r_data); end
        // streaming write of 16 words at 0x100
        start; sbyte(8'h03); sword(32'h00000100);
        for (k = 0; k < 16; k = k + 1) sword(32'hA5000000 + k * 32'h01010101);
        stop;
        repeat (20) @(posedge clk);
        for (k = 0; k < 16; k = k + 1)
            if (mem[64 + k] !== 32'hA5000000 + k * 32'h01010101) begin errs = errs + 1; $display("MEM %0d %h", k, mem[64+k]); end
        // quad streaming write of 16 words at 0x300
        start; sbyte(8'h07); sword(32'h00000300);
        for (k = 0; k < 16; k = k + 1) qword(32'h5A000000 + k * 32'h02020202);
        stop;
        repeat (20) @(posedge clk);
        for (k = 0; k < 16; k = k + 1)
            if (mem[192 + k] !== 32'h5A000000 + k * 32'h02020202) begin errs = errs + 1; $display("QMEM %0d %h", k, mem[192+k]); end
        HR = 40;
        // read back word 5
        start; sbyte(8'h04); sword(32'h00000100 + 4 * 5); rbits(16); rbits(32); stop;
        if (rx !== 32'hA5000000 + 5 * 32'h01010101) begin errs = errs + 1; $display("RD %h", rx); end
        // status
        start; sbyte(8'h05); rbits(8); rbits(8); stop;
        if (rx[1:0] !== 2'b10) begin errs = errs + 1; $display("ST %b", rx[7:0]); end
        // overrun
        full = 1; start; sbyte(8'h03); sword(32'h00000200); sword(32'h11111111); stop; full = 0;
        start; sbyte(8'h05); rbits(8); rbits(8); stop;
        if (rx[1:0] !== 2'b11) begin errs = errs + 1; $display("ST2 %b", rx[7:0]); end
        if (errs == 0) $display("TB_SPI PASS"); else $display("TB_SPI FAIL %0d", errs);
        $finish;
    end
endmodule
