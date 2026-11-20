// ng_boot.v - 1 KiB boot RAM (512 x 16 bit) the 68k reads while the stub runs.
// Written by the MCU (index register + data register with auto-increment),
// optionally preloaded at configuration time from BOOT_HEX (default image, so
// the BIOS sees a valid cartridge before the MCU has finished booting).
// Words are stored as the 68k reads them (big-endian halves already combined).
`timescale 1ns/1ps
module ng_boot #(parameter BOOT_HEX = "") (
    input  wire        clk,
    input  wire        idx_wr,         // load the write index
    input  wire        data_wr,        // write a word at the index, index++
    input  wire [15:0] wdata,
    input  wire [8:0]  raddr,
    output reg  [15:0] rdata
);
    reg [15:0] mem [0:511];
    reg [8:0]  widx;
    integer i;
    initial begin
        for (i = 0; i < 512; i = i + 1) mem[i] = 16'h0000;
        if (BOOT_HEX != "") $readmemh(BOOT_HEX, mem);
    end
    always @(posedge clk) begin
        if (idx_wr) widx <= wdata[8:0];
        if (data_wr) begin mem[widx] <= wdata; widx <= widx + 1; end
        rdata <= mem[raddr];
    end
endmodule
