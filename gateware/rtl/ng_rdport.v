// ng_rdport.v - byte read port (M ROM and V ROM readers).
// rd pulse + byte offset in the region -> byte out and valid pulse.
`timescale 1ns/1ps
module ng_rdport (
    input  wire        clk, rst,
    input  wire        rd,
    input  wire [31:0] offs,            // byte offset inside the region
    input  wire [31:0] base,
    output reg         mem_req,
    output reg  [31:0] mem_addr,
    input  wire        mem_valid,
    input  wire [63:0] mem_rdata,
    output reg  [7:0]  data,
    output reg         valid
);
    reg [2:0] lane;
    always @(posedge clk) begin
        mem_req <= 0; valid <= 0;
        if (rd) begin
            mem_req <= 1; mem_addr <= (base + offs) & 32'hFFFFFFF8;
            lane <= (base + offs);
        end
        if (mem_valid) begin
            valid <= 1;
            data  <= mem_rdata >> {lane, 3'b000};
        end
    end
endmodule
