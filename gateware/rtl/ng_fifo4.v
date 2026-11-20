// Tiny synchronous FIFO, depth 4.
`timescale 1ns/1ps
module ng_fifo4 #(parameter W = 66) (
    input  wire clk, rst, push, pop,
    input  wire [W-1:0] din,
    output wire [W-1:0] dout,
    output wire empty, full
);
    reg [W-1:0] m [0:3];
    reg [2:0] wp, rp;
    assign empty = (wp == rp);
    assign full  = (wp - rp) == 3'd4;
    assign dout  = m[rp[1:0]];
    always @(posedge clk) begin
        if (rst) begin wp <= 0; rp <= 0; end
        else begin
            if (push && !full) begin m[wp[1:0]] <= din; wp <= wp + 1; end
            if (pop && !empty) rp <= rp + 1;
        end
    end
endmodule
