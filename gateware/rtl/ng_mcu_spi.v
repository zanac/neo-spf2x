// ng_mcu_spi.v - SPI slave (mode 0, MSB first) between the MCU and the register /
// SDRAM-write interface of ng_top.  One frame per chip-select.
//
//   0x01 aa dddddddd          register write: aa = 8-bit register, d = 32-bit big-endian
//   0x03 AAAAAAAA {dddddddd}* streaming SDRAM write from byte address A (word aligned,
//                             auto-increment by 4) until CS goes high
//   0x07 AAAAAAAA {nnnnnnnn}* same as 0x03 but after the address the data goes on four
//                             lines (IO0 = mosi, IO1, IO2, IO3), one nibble per SCLK,
//                             most significant nibble first: 4x the throughput, write only
//   0x04 AAAAAAAA <16 dummy clocks> dddddddd   SDRAM word read at A
//   0x05 <8 dummy clocks> ss  status byte: bit0 overrun (MCU FIFO full when a word
//                             arrived: that word was lost), bit1 = run (ng_top)
// The SPI pins are asynchronous: 2-FF synchronisers.  Writes work up to SCLK = clk/4;
// the MISO answer lags the SCLK edge by ~3 clk, so reads (0x04, 0x05) need SCLK <= clk/8
// (about 16 MHz at 133 MHz).  Throughput: 0x07 at 25 MHz = 12.5 MB/s, 0x03 = 3 MB/s.
`timescale 1ns/1ps
module ng_mcu_spi (
    input  wire        clk, rst,
    input  wire        sclk, cs_n, mosi,
    input  wire        io1_in, io2_in, io3_in,    // quad write only
    output wire        miso, miso_oe,
    // register bus (to ng_top)
    output reg         reg_wr,
    output reg  [7:0]  reg_addr,
    output reg  [31:0] reg_wdata,
    input  wire        run,
    // SDRAM access (to ng_top)
    output reg         mcu_req, mcu_we,
    output reg  [31:0] mcu_addr, mcu_wdata,
    input  wire        mcu_full,
    input  wire        mcu_rvalid,
    input  wire [31:0] mcu_rdata
);
    reg [2:0] sc, cs, mo, q1, q2, q3;
    always @(posedge clk) begin
        sc <= {sc[1:0], sclk}; cs <= {cs[1:0], cs_n}; mo <= {mo[1:0], mosi};
        q1 <= {q1[1:0], io1_in}; q2 <= {q2[1:0], io2_in}; q3 <= {q3[1:0], io3_in};
    end
    wire rise = sc[1] & ~sc[2], fall = ~sc[1] & sc[2];
    wire sel = ~cs[1];
    assign miso_oe = sel & ~quad_on;

    localparam S_CMD = 0, S_REGA = 1, S_REGD = 2, S_WA = 3, S_WD = 4, S_RA = 5,
               S_RDUM = 6, S_RD = 7, S_ST = 8, S_IDLE = 9, S_STD = 10, S_QD = 11;
    reg        quad, quad_on;
    reg [3:0]  st;
    reg [5:0]  nb;                 // bits received in the current field
    reg [31:0] sh;                 // receive shift register
    reg [31:0] out;                // transmit shift register
    reg        overrun, skip;
    assign miso = out[31];

    always @(posedge clk) begin
        reg_wr <= 1'b0; mcu_req <= 1'b0;
        if (rst || !sel) begin
            st <= S_CMD; nb <= 0; quad_on <= 1'b0; if (rst) overrun <= 0;
        end else begin
            if (mcu_rvalid) out <= mcu_rdata;                 // read data for state S_RD
            if (fall && (st == S_RD || st == S_ST)) begin
                if (skip) skip <= 1'b0;                   // bit 7 is already on MISO
                else out <= {out[30:0], 1'b0};
            end
            if (rise) begin
                sh <= (st == S_QD) ? {sh[27:0], q3[1], q2[1], q1[1], mo[1]} : {sh[30:0], mo[1]};
                nb <= nb + 1'b1;
                case (st)
                S_CMD: if (nb == 7) begin
                    nb <= 0;
                    case ({sh[6:0], mo[1]})
                    8'h01: st <= S_REGA;
                    8'h03: begin st <= S_WA; quad <= 1'b0; end
                    8'h07: begin st <= S_WA; quad <= 1'b1; end
                    8'h04: st <= S_RA;
                    8'h05: st <= S_STD;
                    default: st <= S_IDLE;
                    endcase
                end
                S_REGA: if (nb == 7) begin reg_addr <= {sh[6:0], mo[1]}; nb <= 0; st <= S_REGD; end
                S_REGD: if (nb == 31) begin
                    reg_wdata <= {sh[30:0], mo[1]}; reg_wr <= 1'b1; nb <= 0; st <= S_IDLE;
                end
                S_WA: if (nb == 31) begin
                    mcu_addr <= {sh[30:0], mo[1]}; nb <= 0;
                    st <= quad ? S_QD : S_WD; quad_on <= quad;
                end
                S_WD: if (nb == 31) begin
                    nb <= 0;
                    if (mcu_full) overrun <= 1'b1;
                    else begin mcu_wdata <= {sh[30:0], mo[1]}; mcu_we <= 1'b1; mcu_req <= 1'b1; end
                end
                S_RA: if (nb == 31) begin
                    mcu_addr <= {sh[30:0], mo[1]}; mcu_we <= 1'b0; mcu_req <= 1'b1;
                    nb <= 0; st <= S_RDUM;
                end
                S_QD: if (nb == 7) begin
                    nb <= 0;
                    if (mcu_full) overrun <= 1'b1;
                    else begin
                        mcu_wdata <= {sh[27:0], q3[1], q2[1], q1[1], mo[1]};
                        mcu_we <= 1'b1; mcu_req <= 1'b1;
                    end
                end
                S_RDUM: if (nb == 15) begin nb <= 0; st <= S_RD; skip <= 1'b1; end
                S_STD: if (nb == 7) begin
                    nb <= 0; st <= S_ST; skip <= 1'b1; out <= {6'd0, run, overrun, 24'd0};
                end
                default: ;
                endcase
            end
            // address auto-increment after a streamed word was issued
            if (mcu_req && mcu_we) mcu_addr <= mcu_addr + 32'd4;
        end
    end
endmodule
