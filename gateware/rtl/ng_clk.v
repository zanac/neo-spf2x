// ng_clk.v - board clock: ECP5 PLL from the 24 MHz console clock (24M, ball A2 = ULC_GPLL1T_IN) to the
// 132 MHz system/SDRAM clock, plus a second output for the SDRAM clock pin and a reset released only
// when the PLL is locked.
//
//   fPFD = 24 / CLKI_DIV(1)            = 24 MHz   (limit: >= 10 MHz)
//   fVCO = 24 * CLKFB_DIV(22) * ...    = 528 MHz  (limit: 400-800 MHz; CLKOP_DIV 4 -> 132 MHz)
//   clk_sys = fVCO / 4 = 132 MHz (tCK 7.58 ns, inside the AS4C32M16SB-7 grade, CL3)
//   clk_sdr = same frequency, phase shifted (SDR_PHASE, 0..7 of 45 degrees steps of the VCO period / 4
//             through CLKOS_CPHASE); the right value depends on the board delays: to be tuned
//             (a first guess of 90 degrees is CPHASE 1 with FPHASE 0) and verified on the bench.
// NOT simulated (Icarus has no ECP5 primitive models); only synthesised/placed with Yosys+nextpnr.
// The Lattice limits above are those of the ECP5 data sheet / TN-02200 as read in this project.
`timescale 1ns/1ps
module ng_clk #(parameter SDR_CPHASE = 1) (
    input  wire clk24,
    output wire clk_sys,
    output wire clk_sdr,
    output wire rst_sys          // synchronous to clk_sys, high until the PLL is locked
);
    wire locked, clkfb;
`ifdef SYNTHESIS
    (* FREQUENCY_PIN_CLKI = "24", FREQUENCY_PIN_CLKOP = "132", FREQUENCY_PIN_CLKOS = "132", ICP_CURRENT = "12", LPF_RESISTOR = "8", MFG_ENABLE_FILTEROPAMP = "1", MFG_GMCREF_SEL = "2" *)
    EHXPLLL #(
        .PLLRST_ENA("DISABLED"), .INTFB_WAKE("DISABLED"), .STDBY_ENABLE("DISABLED"),
        .DPHASE_SOURCE("DISABLED"), .OUTDIVIDER_MUXA("DIVA"), .OUTDIVIDER_MUXB("DIVB"),
        .OUTDIVIDER_MUXC("DIVC"), .OUTDIVIDER_MUXD("DIVD"),
        .CLKI_DIV(1), .CLKOP_ENABLE("ENABLED"), .CLKOP_DIV(4), .CLKOP_CPHASE(1), .CLKOP_FPHASE(0),
        .CLKOS_ENABLE("ENABLED"), .CLKOS_DIV(4), .CLKOS_CPHASE(1 + SDR_CPHASE), .CLKOS_FPHASE(0),
        .FEEDBK_PATH("CLKOP"), .CLKFB_DIV(22)
    ) pll (
        .CLKI(clk24), .CLKFB(clkfb), .PHASESEL1(1'b0), .PHASESEL0(1'b0), .PHASEDIR(1'b0),
        .PHASESTEP(1'b0), .PHASELOADREG(1'b0), .STDBY(1'b0), .PLLWAKESYNC(1'b0),
        .RST(1'b0), .ENCLKOP(1'b1), .ENCLKOS(1'b1),
        .CLKOP(clkfb), .CLKOS(clk_sdr), .LOCK(locked)
    );
    assign clk_sys = clkfb;
`else
    // behavioural stand-in for simulation: 24 MHz x 5.5 is not representable, use the system clock as is
    assign clk_sys = clk24; assign clk_sdr = clk24; assign locked = 1'b1;
`endif
    reg [3:0] sh = 4'hF;
    always @(posedge clk_sys or negedge locked)
        if (!locked) sh <= 4'hF; else sh <= {sh[2:0], 1'b0};
    assign rst_sys = sh[3];
endmodule
