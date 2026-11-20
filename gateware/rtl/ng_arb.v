// ng_arb.v - fixed-priority arbiter in front of ng_sdram.
// Port 0 = MCU (reads and writes, highest), then C, S, P, M, V, ADPCM-A, ADPCM-B.
// Clients push single-cycle requests (addr, and for MCU also we/wdata) and get
// responses in order on their own rvalid/rdata (responses to port 0 included).
`timescale 1ns/1ps
module ng_arb (
    input  wire        clk, rst,
    // client requests
    input  wire [7:0]  c_req,
    input  wire [255:0] c_addr,          // 8 x 32
    input  wire        mcu_we,
    input  wire [31:0] mcu_wdata,
    output wire        mcu_full,
    output wire [7:0]  c_rvalid,
    output wire [63:0] c_rdata,
    // controller
    output reg         req_valid,
    output reg         req_we,
    output reg  [31:0] req_addr,
    output reg  [31:0] req_wdata,
    input  wire        req_ready,
    input  wire        rsp_valid,
    input  wire [63:0] rsp_rdata
);
    wire [7:0]  empty, full;
    wire [64:0] q [0:7];
    reg  [7:0]  pop_sel;
    reg  [2:0]  owner;
    reg         busy;
    genvar g;
    generate for (g = 0; g < 8; g = g + 1) begin : F
        wire [64:0] din = (g == 0) ? {mcu_we, mcu_wdata, c_addr[32*g +: 32]}
                                   : {1'b0, 32'd0, c_addr[32*g +: 32]};
        ng_fifo4 #(.W(65)) f(.clk(clk), .rst(rst), .push(c_req[g]), .pop(pop_sel[g]),
                             .din(din), .dout(q[g]), .empty(empty[g]), .full(full[g]));
    end endgenerate
    assign mcu_full = full[0];

    // priority pick (lowest index wins)
    reg [2:0] pick; reg any;
    integer i;
    always @* begin
        any = 0; pick = 0;
        for (i = 7; i >= 0; i = i - 1)
            if (!empty[i]) begin any = 1; pick = i; end
    end
    always @* begin
        pop_sel = 8'd0;
        if (!busy && any) pop_sel[pick] = 1'b1;
    end

    // the request stays on the controller port until it is accepted
    always @(posedge clk) begin
        if (rst) begin busy <= 0; req_valid <= 0; end
        else begin
            if (!busy && any) begin
                req_valid <= 1'b1;
                req_addr  <= q[pick][31:0];
                req_wdata <= q[pick][63:32];
                req_we    <= q[pick][64];
                owner     <= pick;
                busy      <= 1'b1;
            end else if (req_valid && req_ready) req_valid <= 1'b0;
            if (rsp_valid) busy <= 1'b0;
        end
    end
    assign c_rvalid = (rsp_valid && busy) ? (8'd1 << owner) : 8'd0;
    assign c_rdata  = rsp_rdata;
endmodule
