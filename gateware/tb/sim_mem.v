// Fixed-latency word memory, in-order responses.  Image: sdram.hex (32-bit words).
`timescale 1ns/1ps
module sim_mem #(parameter LAT = 6, parameter NWORDS = 65536) (
    input  wire clk, input wire req, input wire [31:0] addr,
    output reg valid, output reg [63:0] rdata);
    reg [31:0] mem [0:NWORDS-1];
    reg [63:0] pd [0:15]; reg pv [0:15]; integer i;
    initial $readmemh("sdram.hex", mem);
    always @(posedge clk) begin
        for (i = 15; i > 0; i = i - 1) begin pd[i] <= pd[i-1]; pv[i] <= pv[i-1]; end
        pv[0] <= req; pd[0] <= {mem[((addr[31:3] << 1) + 1) % NWORDS], mem[(addr[31:3] << 1) % NWORDS]};
        valid <= pv[LAT-1]; rdata <= pd[LAT-1];
    end
endmodule
