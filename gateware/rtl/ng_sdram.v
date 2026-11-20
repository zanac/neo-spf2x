// ng_sdram.v - SDR SDRAM controller, 16-bit chip, 4 banks, CL3, burst 4.
// Reads return 8 aligned bytes (one ACT + one burst of 4 beats); sprite and fix
// fetches are exactly that.  Writes store one 32-bit word (addr[2] picks the
// half of the burst, the other beats are masked).  Closed page
// (auto-precharge), one request in flight.
//
// Byte address map (64 MiB part, e.g. 32M x 16):
//   a16 = addr[25:1];  col = a16[9:0], bank = a16[11:10], row = a16[24:12]
// Two chips share the bus (profile ngsd-128M): addr[26] selects the chip with
// sd_cs_n[addr[26]].  Init and refresh go to both chips at once (CS low on both);
// ACTIVE/READ/WRITE only to the selected one.  With one chip fitted use sd_cs_n[0].
// Request: raise req_valid with req_we/req_addr/req_wdata; transfer happens on
// the edge where req_valid & req_ready.  rsp_valid pulses when a read's data
// (rsp_rdata, 64 bit) is ready or a write has been issued completely.
`timescale 1ns/1ps
module ng_sdram #(
    parameter TRCD = 3, CL = 3, TRC = 8, TRP = 3, TRFC = 8, TWR = 2,
    parameter REFI = 700,            // clk cycles between refreshes
    parameter INIT_CLKS = 64         // power-up wait (real part: >= 100 us)
) (
    input  wire        clk, rst,
    input  wire        req_valid,
    input  wire        req_we,
    input  wire [31:0] req_addr,
    input  wire [31:0] req_wdata,
    output wire        req_ready,
    output reg         rsp_valid,
    output reg  [63:0] rsp_rdata,
    // chip pins
    output reg  [1:0]  sd_cs_n,
    output reg         sd_ras_n, sd_cas_n, sd_we_n,
    output reg  [1:0]  sd_ba,
    output reg  [12:0] sd_a,
    output reg  [1:0]  sd_dqm,
    output reg  [15:0] sd_dq_o,
    output reg         sd_dq_oe,
    input  wire [15:0] sd_dq_i
);
    localparam GAP_W = TRCD + 4 + TWR + TRP;           // after a write
    localparam [3:0] S_INIT=0, S_PRE=1, S_W1=2, S_REF1=3, S_W2=4, S_REF2=5,
                     S_W3=6, S_MRS=7, S_W4=8, S_IDLE=9, S_ACT=10, S_RD=11,
                     S_WR=12, S_RFC=13;
    reg [3:0]  st;
    reg [15:0] cnt;                  // cycles since the last ACT / state entry
    reg [15:0] refc;
    reg [1:0]  wcnt;
    reg        refp;
    reg        l_we;
    reg [31:0] l_addr, l_wd;
    wire [24:0] a16 = l_addr[25:1];

    reg [15:0] gap;                  // required distance ACT -> next ACT
    wire idle_ok = (st == S_IDLE) && (cnt >= gap) && !refp;
    assign req_ready = idle_ok;

    task cmd(input c_ras, input c_cas, input c_we);
        begin sd_ras_n <= c_ras; sd_cas_n <= c_cas; sd_we_n <= c_we; end
    endtask

    always @(posedge clk) begin
        sd_cs_n <= 2'b00; sd_ras_n <= 1'b1; sd_cas_n <= 1'b1; sd_we_n <= 1'b1;
        sd_dqm <= 2'b00; sd_dq_oe <= 1'b0; rsp_valid <= 1'b0;
        if (rst) begin
            st <= S_INIT; cnt <= 0; refc <= 0; refp <= 0; gap <= 0;
        end else begin
            // refresh timer (runs once initialised)
            if (st >= S_IDLE) begin
                if (refc >= REFI - 1) begin refc <= 0; refp <= 1; end
                else refc <= refc + 1;
            end
            cnt <= cnt + 1;
            case (st)
            S_INIT: if (cnt >= INIT_CLKS) begin
                        cmd(0, 1, 0); sd_a <= 13'h0400; st <= S_PRE; cnt <= 0; end
            S_PRE:  begin st <= S_W1; cnt <= 0; end
            S_W1:   if (cnt >= TRP) begin cmd(0, 0, 1); st <= S_REF1; cnt <= 0; end
            S_REF1: begin st <= S_W2; cnt <= 0; end
            S_W2:   if (cnt >= TRFC) begin cmd(0, 0, 1); st <= S_REF2; cnt <= 0; end
            S_REF2: begin st <= S_W3; cnt <= 0; end
            S_W3:   if (cnt >= TRFC) begin
                        cmd(0, 0, 0); sd_ba <= 0; sd_a <= 13'h032; // CL3 BL4
                        st <= S_MRS; cnt <= 0; end
            S_MRS:  begin st <= S_W4; cnt <= 0; end
            S_W4:   if (cnt >= 3) begin st <= S_IDLE; cnt <= 16'd1000; gap <= 0; end
            S_IDLE: begin
                if (cnt >= gap) begin
                    if (refp) begin
                        cmd(0, 0, 1); refp <= 0; st <= S_RFC; cnt <= 0;
                    end else if (req_valid) begin
                        cmd(0, 1, 1);                       // ACTIVE
                        sd_cs_n <= req_addr[26] ? 2'b01 : 2'b10;
                        sd_ba <= req_addr[12:11]; sd_a <= req_addr[25:13];
                        l_we <= req_we; l_addr <= req_addr; l_wd <= req_wdata;
                        st <= S_ACT; cnt <= 1;
                    end
                end
            end
            S_RFC:  if (cnt >= TRFC) begin st <= S_IDLE; cnt <= 16'd1000; gap <= 0; end
            S_ACT: if (cnt == TRCD) begin
                        // READ/WRITE with auto-precharge (A10 = 1)
                        sd_ba <= l_addr[12:11];
                        sd_a  <= {2'b00, 1'b1, l_addr[10:3], 2'b00};
                        wcnt  <= 0;
                        sd_cs_n <= l_addr[26] ? 2'b01 : 2'b10;
                        if (l_we) begin
                            cmd(1, 0, 0); sd_dq_oe <= 1'b1;
                            sd_dq_o <= l_addr[2] ? 16'h0 : l_wd[15:0];
                            sd_dqm  <= l_addr[2] ? 2'b11 : 2'b00;
                            st <= S_WR; gap <= GAP_W;
                        end else begin
                            cmd(1, 0, 1); st <= S_RD; gap <= TRC;
                        end
                    end
            S_WR:   begin                     // beats 1..3 of the burst
                        sd_dq_oe <= 1'b1;
                        case (wcnt)
                        0: begin sd_dq_o <= l_addr[2] ? 16'h0 : l_wd[31:16];
                                 sd_dqm <= l_addr[2] ? 2'b11 : 2'b00; end
                        1: begin sd_dq_o <= l_addr[2] ? l_wd[15:0] : 16'h0;
                                 sd_dqm <= l_addr[2] ? 2'b00 : 2'b11; end
                        default: begin sd_dq_o <= l_addr[2] ? l_wd[31:16] : 16'h0;
                                 sd_dqm <= l_addr[2] ? 2'b00 : 2'b11;
                                 rsp_valid <= 1'b1; st <= S_IDLE; end
                        endcase
                        wcnt <= wcnt + 1;
                    end
            S_RD:   begin
                        // READ was issued at edge E (cnt = TRCD there); data is
                        // sampled at E+CL+1 and E+CL+2
                        if (cnt == TRCD + CL + 1) rsp_rdata[15:0]  <= sd_dq_i;
                        if (cnt == TRCD + CL + 2) rsp_rdata[31:16] <= sd_dq_i;
                        if (cnt == TRCD + CL + 3) rsp_rdata[47:32] <= sd_dq_i;
                        if (cnt == TRCD + CL + 4) rsp_rdata[63:48] <= sd_dq_i;
                        if (cnt == TRCD + CL + 5) begin
                            rsp_valid <= 1'b1; st <= S_IDLE; end
                    end
            endcase
        end
    end
endmodule
