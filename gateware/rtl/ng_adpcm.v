// ng_adpcm.v - one YM2610 ADPCM ROM bus (A: SDRAD/SDRA/SDRMPX/SDROE, B: SDPAD/SDPA/
// SDPMPX/SDPOE) as seen from the cartridge.  Written from the neogeodev wiki page
// "YM2610 ADPCM bus" (docs/TIMING.md s.11); the exact bit mapping is the page's, the
// nanosecond margins are not documented and not verified on hardware.
//
// Cycle (periods of 1.5 us on A, 250 ns on B): address LSBs set, MPX rises, address
// MSBs set, MPX falls, OE_n falls (the bus turns into a data bus driven by the ROM),
// the console latches the data on the rising edge of OE_n.
//   A: {A[9:0]}  = {SDRA9, SDRA8, SDRAD[7:0]} at MPX rise
//      {A[19:10]} = same pins at MPX fall;  A[23:20] = SDRA23..20 (direct)
//   B: {A[11:0]}  = {SDPA11..8, SDPAD[7:0]} at MPX rise
//      {A[23:12]} = same pins at MPX fall
// The read is issued to the V region when MPX falls; the data is driven while OE_n is
// low.  `late` counts OE_n falling before the data arrived (SDRAM too slow): the old
// byte is then driven, which is what a real slow ROM would do.
`timescale 1ns/1ps
module ng_adpcm #(parameter B = 0) (
    input  wire        clk, rst,
    input  wire        mpx, oe_n,
    input  wire [7:0]  ad_in,
    input  wire [3:0]  a_mid,        // A: {2'b0, SDRA9, SDRA8}   B: SDPA11..SDPA8
    input  wire [3:0]  a_top,        // A: SDRA23..SDRA20          B: unused
    output wire [7:0]  ad_out,
    output wire        ad_drive,     // 1 while the cartridge drives the AD pins
    // byte read port (ng_rdport)
    output reg         rd,
    output reg  [31:0] offs,
    input  wire [7:0]  rdata,
    input  wire        rvalid,
    output reg  [15:0] late
);
    reg [1:0] m_s, o_s;               // synchronisers (mpx, oe_n); the address pins
    reg [7:0] d_s0, d_s1; reg [3:0] g_s0, g_s1, t_s0, t_s1;   // use the same delay
    reg       m_d;
    always @(posedge clk) begin
        m_s <= {m_s[0], mpx}; o_s <= {o_s[0], oe_n};
        d_s0 <= ad_in; d_s1 <= d_s0; g_s0 <= a_mid; g_s1 <= g_s0; t_s0 <= a_top; t_s1 <= t_s0;
        m_d <= m_s[1];
    end
    wire m_rise = m_s[1] & ~m_d, m_fall = ~m_s[1] & m_d;
    wire oe_low = ~o_s[1];
    reg  oe_d; always @(posedge clk) oe_d <= oe_low;

    reg [11:0] lo;
    reg [7:0]  dat;
    reg        got;
    always @(posedge clk) begin
        rd <= 1'b0;
        if (rst) begin got <= 0; late <= 0; end
        else begin
            if (m_rise) lo <= B ? {g_s1, d_s1} : {2'b00, g_s1[1:0], d_s1};
            if (m_fall) begin
                offs <= B ? {8'd0, g_s1, d_s1, lo}
                          : {8'd0, t_s1, g_s1[1:0], d_s1, lo[9:0]};
                rd <= 1'b1; got <= 1'b0;
            end
            if (rvalid) begin dat <= rdata; got <= 1'b1; end
            if (oe_low && !oe_d && !got) late <= late + 1'b1;
        end
    end
    assign ad_out   = dat;
    assign ad_drive = oe_low;
endmodule
